import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from .audit import record
from .config import ENV, ORIGINS
from .db import get_db
from .errors import AppError
from .models import Session, UsedRefresh, User, now
from .schemas import Login
from .responses import SessionTokens, UserView
from .security import PERMISSIONS, check_password, current_user, hasher, issue_session, token_hash

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def user_info(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "permissions": sorted(PERMISSIONS[user.role]),
    }


def set_refresh(response, token):
    response.set_cookie(
        "lcv_refresh",
        token,
        httponly=True,
        secure=ENV == "production",
        samesite="strict",
        max_age=28800,
        path="/api/v1/auth",
    )


def check_origin(request):
    if request.headers.get("origin") not in ORIGINS or request.headers.get("x-lcv-client") != "workbench":
        raise AppError(
            403, "CSRF_REJECTED", "Refresh requests require the trusted application origin and client header"
        )


@router.post("/login", response_model=SessionTokens)
def login(body: Login, request: Request, response: Response, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()).with_for_update())
    valid = check_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not user.active or not valid or (user.locked_until and user.locked_until > now()):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now() + timedelta(minutes=min(30, user.failed_logins))
        record(
            db,
            user,
            "LOGIN_FAILED",
            user.id if user else "unknown",
            {"result": "DENIED"},
            request.state.correlation_id,
        )
        db.commit()
        raise AppError(401, "LOGIN_FAILED", "Invalid credentials or account temporarily locked")
    user.failed_logins, user.locked_until, user.last_login = 0, None, now()
    session, access, refresh = issue_session(db, user, request.headers.get("user-agent", "unknown"))
    set_refresh(response, refresh)
    record(db, user, "LOGIN", session.id, {"result": "SUCCESS"}, request.state.correlation_id)
    return {"access_token": access, "token_type": "bearer", "expires_in": 900, "user": user_info(user)}


@router.post("/refresh", response_model=SessionTokens)
def refresh(request: Request, response: Response, db=Depends(get_db)):
    check_origin(request)
    hashed = token_hash(request.cookies.get("lcv_refresh", ""))
    consumed = db.get(UsedRefresh, hashed)
    if consumed:
        session = db.get(Session, consumed.session_id)
        session.revoked = True
        record(
            db,
            db.get(User, session.user_id),
            "REFRESH_REPLAY_BLOCKED",
            session.id,
            {},
            request.state.correlation_id,
        )
        db.commit()
        raise AppError(401, "TOKEN_REPLAY", "Token reuse detected; session revoked")
    session = db.scalar(select(Session).where(Session.refresh_hash == hashed).with_for_update())
    user = db.get(User, session.user_id) if session else None
    if not session or session.revoked or session.refresh_expires <= now() or not user.active:
        raise AppError(401, "SESSION_EXPIRED", "Please sign in again")
    access, refresh = secrets.token_urlsafe(40), secrets.token_urlsafe(48)
    db.add(UsedRefresh(token_hash=hashed, session_id=session.id))
    session.access_hash, session.refresh_hash = token_hash(access), token_hash(refresh)
    session.access_expires = now() + timedelta(minutes=15)
    set_refresh(response, refresh)
    return {"access_token": access, "token_type": "bearer", "expires_in": 900, "user": user_info(user)}


@router.get("/me", response_model=UserView)
def me(user=Depends(current_user)):
    return user_info(user)


@router.post("/logout")
def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)):
    request.state.session.revoked = True
    response.delete_cookie("lcv_refresh", path="/api/v1/auth")
    record(db, user, "LOGOUT", request.state.session.id, {}, request.state.correlation_id)
    return {"message": "Signed out"}


@router.get("/sessions")
def sessions(user=Depends(current_user), db=Depends(get_db)):
    return [
        {"id": s.id, "device": s.device, "created_at": s.created_at, "expires_at": s.refresh_expires}
        for s in db.scalars(
            select(Session).where(
                Session.user_id == user.id, Session.revoked.is_(False), Session.refresh_expires > now()
            )
        )
    ]


@router.delete("/sessions/{session_id}")
def revoke(session_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    session = db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise AppError(404, "NOT_FOUND", "Session not found")
    session.revoked = True
    record(db, user, "SESSION_REVOKED", session.id, {}, request.state.correlation_id)
    return {"message": "Session revoked"}

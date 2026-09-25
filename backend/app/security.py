import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from .db import get_db
from .errors import AppError
from .models import LC, Session, User, now

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
READ = {"LC_VIEW", "DOCUMENT_VIEW", "RULE_VIEW", "REPORT_VIEW"}
PERMISSIONS = {
    "TRADE_ANALYST": READ
    | {
        "LC_CREATE",
        "LC_UPDATE",
        "LC_SUBMIT",
        "DOCUMENT_CREATE",
        "VALIDATION_RUN",
        "CASE_COMMENT",
        "EXPORT_DATA",
    },
    "COMPLIANCE_REVIEWER": READ
    | {
        "CASE_REVIEW",
        "CASE_REJECT",
        "CASE_ESCALATE",
        "CASE_COMMENT",
        "VALIDATION_RUN",
        "AUDIT_VIEW",
        "EXPORT_DATA",
    },
    "SENIOR_CHECKER": READ
    | {
        "CASE_REVIEW",
        "CASE_APPROVE",
        "CASE_REJECT",
        "CASE_ESCALATE",
        "CASE_OVERRIDE",
        "CASE_COMMENT",
        "AUDIT_VIEW",
        "EXPORT_DATA",
    },
    "COMPLIANCE_MANAGER": READ
    | {
        "CASE_REVIEW",
        "CASE_ASSIGN",
        "CASE_ESCALATE",
        "CASE_REJECT",
        "CASE_COMMENT",
        "CASE_OVERRIDE",
        "RULE_CONFIGURE",
        "AUDIT_VIEW",
        "EXPORT_DATA",
    },
    "INTERNAL_AUDITOR": READ | {"AUDIT_VIEW", "AUDIT_VERIFY", "EXPORT_DATA"},
    "EXECUTIVE_VIEWER": {"LC_VIEW", "REPORT_VIEW"},
    "SYSTEM_ADMIN": {
        "USER_MANAGE",
        "RULE_VIEW",
        "RULE_CONFIGURE",
        "SYSTEM_CONFIGURE",
        "AUDIT_VIEW",
        "AUDIT_VERIFY",
    },
}


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_valid(password: str):
    if (
        len(password) < 12
        or not any(c.isupper() for c in password)
        or not any(c.islower() for c in password)
        or not any(c.isdigit() for c in password)
    ):
        raise AppError(422, "PASSWORD_POLICY", "Use at least 12 characters with upper/lowercase and a number")


def check_password(password, stored):
    try:
        return hasher.verify(stored, password)
    except VerificationError:
        return False


def issue_session(db, user, device):
    access, refresh = secrets.token_urlsafe(40), secrets.token_urlsafe(48)
    session = Session(
        user_id=user.id,
        access_hash=token_hash(access),
        refresh_hash=token_hash(refresh),
        access_expires=now() + timedelta(minutes=15),
        refresh_expires=now() + timedelta(hours=8),
        device=device[:200],
    )
    db.add(session)
    db.flush()
    return session, access, refresh


def current_user(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)
):
    if not credentials:
        raise AppError(401, "AUTH_REQUIRED", "Please sign in to continue")
    session = db.scalar(
        select(Session).where(
            Session.access_hash == token_hash(credentials.credentials),
            Session.revoked.is_(False),
            Session.access_expires > now(),
        )
    )
    user = db.get(User, session.user_id) if session else None
    if not user or not user.active:
        raise AppError(401, "SESSION_EXPIRED", "Your session has expired. Please sign in again")
    request.state.user = user
    request.state.session = session
    return user


def require(permission):
    def dependency(user=Depends(current_user)):
        if permission not in PERMISSIONS.get(user.role, set()):
            raise AppError(403, "PERMISSION_DENIED", "Your role cannot perform this operation")
        return user

    return dependency


def scope(query, user):
    if user.role == "TRADE_ANALYST":
        return query.where((LC.created_by == user.id) | (LC.assigned_to == user.id))
    if user.role == "COMPLIANCE_REVIEWER":
        return query.where(LC.assigned_to == user.id)
    return query


def get_lc(db, user, lc_id, lock=False):
    query = scope(select(LC).where(LC.id == lc_id), user)
    if lock:
        query = query.with_for_update()
    lc = db.scalar(query)
    if not lc:
        raise AppError(404, "CASE_NOT_FOUND", "Case does not exist or is outside your workspace")
    return lc


def check_version(lc, version):
    if lc.version != version:
        raise AppError(409, "STALE_VERSION", "This case changed. Refresh and review the latest version")

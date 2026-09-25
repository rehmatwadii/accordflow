from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from typing import Literal
from sqlalchemy import func, select

from rules_engine import CATALOG

from .audit import record, verify
from .db import get_db
from .errors import AppError
from .models import (
    AuditEvent,
    Incident,
    Notification,
    OutboxEvent,
    RuleConfig,
    RuleVersion,
    Session,
    Setting,
    User,
    now,
)
from .schemas import ConfigureRule, ResetPassword, StrictModel, UserCreate, UserUpdate
from .security import PERMISSIONS, current_user, hasher, password_valid, require
from .services import serialize

router = APIRouter(prefix="/api/v1", tags=["Governance"])


@router.post("/users", status_code=201)
def create_user(
    body: UserCreate, request: Request, actor=Depends(require("USER_MANAGE")), db=Depends(get_db)
):
    password_valid(body.password)
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise AppError(409, "DUPLICATE_USER", "A demo account already uses this email")
    user = User(
        name=body.name,
        email=body.email.lower(),
        role=body.role.value,
        password_hash=hasher.hash(body.password),
    )
    db.add(user)
    db.flush()
    record(
        db,
        actor,
        "USER_CREATED",
        user.id,
        {"email": user.email, "role": user.role, "reason": body.reason},
        request.state.correlation_id,
    )
    return serialize(user, ("password_hash",))


@router.put("/users/{user_id}/password")
def reset_password(
    user_id: str,
    body: ResetPassword,
    request: Request,
    actor=Depends(require("USER_MANAGE")),
    db=Depends(get_db),
):
    from .config import ENV

    if ENV == "production":
        raise AppError(
            403, "IDENTITY_PROVIDER_REQUIRED", "Production recovery must use the approved identity provider"
        )
    password_valid(body.password)
    user = db.get(User, user_id)
    if not user:
        raise AppError(404, "NOT_FOUND", "User not found")
    user.password_hash = hasher.hash(body.password)
    user.failed_logins, user.locked_until = 0, None
    for session in db.scalars(select(Session).where(Session.user_id == user.id)):
        session.revoked = True
    record(
        db,
        actor,
        "DEMO_PASSWORD_RESET",
        user.id,
        {"reason": body.reason, "sessions_revoked": True},
        request.state.correlation_id,
    )
    return {"message": "Demo password reset and sessions revoked"}


@router.get("/incidents")
def incidents(user=Depends(require("SYSTEM_CONFIGURE")), db=Depends(get_db)):
    return [
        serialize(i) for i in db.scalars(select(Incident).order_by(Incident.created_at.desc()).limit(100))
    ]


class IncidentDecision(StrictModel):
    status: Literal["INVESTIGATING", "RESOLVED", "ESCALATED"]
    reason: str = Field(min_length=10, max_length=1000)


@router.patch("/incidents/{incident_id}")
def decide_incident(
    incident_id: str,
    body: IncidentDecision,
    request: Request,
    user=Depends(require("SYSTEM_CONFIGURE")),
    db=Depends(get_db),
):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise AppError(404, "NOT_FOUND", "Signal not found")
    previous = incident.status
    incident.status, incident.decision = body.status, body.reason
    incident.resolved_at = now() if body.status == "RESOLVED" else None
    record(
        db,
        user,
        "SECURITY_SIGNAL_DECISION",
        incident.id,
        {"before": previous, "after": body.status, "reason": body.reason},
        request.state.correlation_id,
    )
    return serialize(incident)


@router.get("/jobs")
def jobs(user=Depends(require("SYSTEM_CONFIGURE")), db=Depends(get_db)):
    counts = dict(db.execute(select(OutboxEvent.state, func.count()).group_by(OutboxEvent.state)).all())
    return {
        "counts": counts,
        "provider": "Mock email; external transmission suppressed",
        "items": [
            serialize(e)
            for e in db.scalars(select(OutboxEvent).order_by(OutboxEvent.created_at.desc()).limit(30))
        ],
    }


@router.post("/jobs/run")
def run_jobs(request: Request, user=Depends(require("SYSTEM_CONFIGURE")), db=Depends(get_db)):
    from .jobs import deliver, monitor

    result = {**monitor(db), **deliver(db)}
    record(db, user, "WORKER_CYCLE_REQUESTED", "jobs", result, request.state.correlation_id)
    return result


@router.get("/rules")
def rules(user=Depends(require("RULE_VIEW")), db=Depends(get_db)):
    configs = {r.id: r for r in db.scalars(select(RuleConfig))}
    return [
        {
            "id": r[0],
            "name": r[1],
            "category": r[2],
            "description": r[4],
            "severity": configs[r[0]].severity,
            "enabled": configs[r[0]].enabled,
            "version": configs[r[0]].version,
            "kind": "CONFIGURABLE RULE",
            "engine_version": "1.0",
        }
        for r in CATALOG
    ]


@router.patch("/rules/{rule_id}")
def configure(
    rule_id: str,
    body: ConfigureRule,
    request: Request,
    user=Depends(require("RULE_CONFIGURE")),
    db=Depends(get_db),
):
    rule = db.get(RuleConfig, rule_id)
    if not rule:
        raise AppError(404, "NOT_FOUND", "Rule not found")
    if rule.version != body.version:
        raise AppError(409, "STALE_VERSION", "Rule changed; refresh before saving")
    previous = serialize(rule)
    rule.severity, rule.enabled = body.severity, body.enabled
    db.flush()
    db.add(
        RuleVersion(
            rule_id=rule.id,
            version=rule.version,
            configuration=serialize(rule),
            actor_id=user.id,
            reason=body.reason,
        )
    )
    record(
        db,
        user,
        "RULE_CHANGED",
        rule.id,
        {"before": previous, "after": serialize(rule), "reason": body.reason},
        request.state.correlation_id,
    )
    return serialize(rule)


@router.get("/rules/{rule_id}/history")
def rule_history(rule_id: str, user=Depends(require("RULE_VIEW")), db=Depends(get_db)):
    return [
        serialize(v)
        for v in db.scalars(
            select(RuleVersion).where(RuleVersion.rule_id == rule_id).order_by(RuleVersion.version.desc())
        )
    ]


@router.get("/audit")
def audit(
    q: str = Query("", max_length=150),
    entity_id: str = Query("", max_length=60),
    actor: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    user=Depends(require("AUDIT_VIEW")),
    db=Depends(get_db),
):
    query = select(AuditEvent)
    if q:
        query = query.where(AuditEvent.action.contains(q, autoescape=True))
    if entity_id:
        query = query.where(AuditEvent.entity_id == entity_id)
    if actor:
        query = query.where(AuditEvent.actor == actor)
    # Reviewers may inspect only the cases assigned to them and their own authentication events.
    if user.role == "COMPLIANCE_REVIEWER":
        from .models import LC

        query = query.where(
            (AuditEvent.entity_id.in_(select(LC.id).where(LC.assigned_to == user.id)))
            | (AuditEvent.actor == user.email)
        )
    return {
        "items": [
            serialize(e)
            for e in db.scalars(query.order_by(AuditEvent.id.desc()).offset((page - 1) * 30).limit(30))
        ],
        "total": db.scalar(select(func.count()).select_from(query.subquery())),
        "page": page,
    }


@router.post("/audit/verify")
def verify_audit(user=Depends(require("AUDIT_VERIFY")), db=Depends(get_db)):
    return verify(db)


@router.get("/users")
def users(user=Depends(require("USER_MANAGE")), db=Depends(get_db)):
    return [serialize(u, ("password_hash",)) for u in db.scalars(select(User).order_by(User.name))]


@router.patch("/users/{user_id}")
def change_user(
    user_id: str,
    body: UserUpdate,
    request: Request,
    actor=Depends(require("USER_MANAGE")),
    db=Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise AppError(404, "NOT_FOUND", "User not found")
    if user.id == actor.id:
        raise AppError(409, "SELF_ADMIN", "Administrators cannot change their own privileges")
    previous = {"role": user.role, "active": user.active}
    user.role, user.active = body.role.value, body.active
    for session in db.scalars(select(Session).where(Session.user_id == user.id)):
        session.revoked = True
    record(
        db,
        actor,
        "USER_CHANGED",
        user.id,
        {"before": previous, "after": {"role": user.role, "active": user.active}, "reason": body.reason},
        request.state.correlation_id,
    )
    return serialize(user, ("password_hash",))


@router.get("/roles")
def roles(user=Depends(current_user)):
    return {k: sorted(v) for k, v in PERMISSIONS.items()}


@router.get("/notifications")
def notifications(user=Depends(current_user), db=Depends(get_db)):
    return [
        serialize(n)
        for n in db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ]


@router.patch("/notifications/{notification_id}/read")
def read_notification(notification_id: str, user=Depends(current_user), db=Depends(get_db)):
    note = db.get(Notification, notification_id)
    if not note or note.user_id != user.id:
        raise AppError(404, "NOT_FOUND", "Notification not found")
    note.read = True
    return {"read": True}


class SLAConfig(StrictModel):
    standard_hours: int
    high_hours: int
    critical_hours: int
    version: int
    reason: str


@router.get("/settings")
def settings(user=Depends(require("SYSTEM_CONFIGURE")), db=Depends(get_db)):
    return [serialize(s) for s in db.scalars(select(Setting))]


@router.put("/settings/sla")
def configure_sla(
    body: SLAConfig, request: Request, user=Depends(require("SYSTEM_CONFIGURE")), db=Depends(get_db)
):
    if (
        not 1 <= body.critical_hours <= body.high_hours <= body.standard_hours <= 720
        or not 10 <= len(body.reason) <= 1000
    ):
        raise AppError(422, "INVALID_SLA", "Use ordered SLA hours between 1 and 720 and a meaningful reason")
    setting = db.get(Setting, "sla_hours")
    if setting.version != body.version:
        raise AppError(409, "STALE_VERSION", "Configuration changed; refresh")
    previous = setting.value
    setting.value = {
        "STANDARD": body.standard_hours,
        "HIGH": body.high_hours,
        "CRITICAL": body.critical_hours,
    }
    record(
        db,
        user,
        "CONFIGURATION_CHANGED",
        setting.key,
        {"before": previous, "after": setting.value, "reason": body.reason},
        request.state.correlation_id,
    )
    db.flush()
    return serialize(setting)

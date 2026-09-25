"""Local bounded worker with transactional outbox, backoff, and terminal failure state."""

from datetime import timedelta

from sqlalchemy import select

from .audit import record
from .models import AuditEvent, Incident, LC, OutboxEvent, User, now
from .providers import MockEmailProvider, notifications
from .services import sla


def monitor(db):
    counts = {"sla_events": 0, "security_signals": 0}
    cases = db.scalars(
        select(LC).where(LC.status.not_in(["APPROVED", "REJECTED", "CLOSED"])).with_for_update()
    ).all()
    for lc in cases:
        status = sla(lc)
        if status not in {"AT_RISK", "BREACHED"}:
            continue
        key = f"SLA:{lc.id}:{lc.due_at.isoformat()}:{status}"
        if db.scalar(select(OutboxEvent).where(OutboxEvent.event_key == key)):
            continue
        db.add(
            OutboxEvent(
                event_key=key,
                event_type="SLA_" + status,
                payload={"lc_id": lc.id, "reference": lc.reference},
                state="DELIVERED",
                processed_at=now(),
                outcome="In-app notice saved transactionally",
            )
        )
        notifications.send(
            db,
            lc.assigned_to or lc.created_by,
            lc.id,
            f"{lc.reference}: SLA {status.lower().replace('_', ' ')}; review required",
        )
        if status == "BREACHED":
            for manager in db.scalars(
                select(User).where(User.role == "COMPLIANCE_MANAGER", User.active.is_(True))
            ):
                notifications.send(db, manager.id, lc.id, f"SLA escalation: {lc.reference} is overdue")
        record(
            db,
            None,
            "SLA_" + status,
            lc.id,
            {
                "due_at": lc.due_at.isoformat(),
                "policy": "Notification escalation; no autonomous business decision",
            },
        )
        counts["sla_events"] += 1
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action.in_(["REFRESH_REPLAY_BLOCKED", "LOGIN_FAILED"]))
        .order_by(AuditEvent.id.desc())
        .limit(500)
    ).all()
    for event in events:
        key = f"AUDIT:{event.id}"
        if db.scalar(select(Incident).where(Incident.source_key == key)):
            continue
        user = db.scalar(select(User).where(User.email == event.actor))
        if event.action == "LOGIN_FAILED" and (not user or user.failed_logins < 5):
            continue
        db.add(
            Incident(
                source_key=key,
                title="Refresh-token replay"
                if event.action == "REFRESH_REPLAY_BLOCKED"
                else "Repeated authentication failure",
                details={
                    "actor": event.actor,
                    "audit_event": event.id,
                    "correlation_id": event.correlation_id,
                    "classification": "Operational risk signal; not a definitive fraud determination",
                },
            )
        )
        counts["security_signals"] += 1
    db.flush()
    return counts


def deliver(db, provider=None):
    provider = provider or MockEmailProvider()
    events = db.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.state.in_(["PENDING", "RETRY"]), OutboxEvent.next_attempt <= now())
        .order_by(OutboxEvent.created_at)
        .limit(100)
        .with_for_update(skip_locked=True)
    ).all()
    counts = {"delivered": 0, "retried": 0, "dead": 0}
    for event in events:
        event.attempts += 1
        try:
            provider.send(db, **event.payload)
            event.state, event.processed_at, event.outcome = (
                "DELIVERED",
                now(),
                "Mock provider: external transmission suppressed",
            )
            counts["delivered"] += 1
        except Exception:
            event.state = "DEAD" if event.attempts >= 3 else "RETRY"
            event.next_attempt = now() + timedelta(seconds=30 * 2**event.attempts)
            event.outcome = "Provider failed; details suppressed"
            counts["dead" if event.state == "DEAD" else "retried"] += 1
    db.flush()
    return counts

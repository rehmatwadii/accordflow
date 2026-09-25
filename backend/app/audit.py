"""Transactional hash chain. The singleton head serializes appenders on PostgreSQL."""

import hashlib
import json

from sqlalchemy import select, update

from .models import AuditEvent, AuditHead, now


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def payload(event):
    return {
        key: getattr(event, key)
        for key in (
            "id",
            "timestamp",
            "actor",
            "role",
            "action",
            "entity_id",
            "details",
            "correlation_id",
            "previous_hash",
        )
    }


def record(db, actor, action: str, entity_id: str, details: dict, correlation_id="SYSTEM"):
    # UPDATE takes a write lock on both supported databases, held until commit.
    db.execute(update(AuditHead).where(AuditHead.id == 1).values(sequence=AuditHead.sequence + 1))
    head = db.scalar(select(AuditHead).where(AuditHead.id == 1).execution_options(populate_existing=True))
    event = AuditEvent(
        id=head.sequence,
        timestamp=now(),
        actor=actor.email if actor else "system",
        role=actor.role if actor else "SYSTEM",
        action=action,
        entity_id=entity_id,
        details=details,
        correlation_id=correlation_id,
        previous_hash=head.hash,
    )
    event.event_hash = digest(payload(event))
    head.hash = event.event_hash
    db.add(event)
    db.flush()
    return event


def verify(db):
    head = db.scalar(select(AuditHead).where(AuditHead.id == 1).with_for_update())
    previous = "0" * 64
    count = 0
    for event in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        count += 1
        if event.id != count or event.previous_hash != previous or event.event_hash != digest(payload(event)):
            return {"status": "FAIL", "checked": count, "failed_event": event.id}
        previous = event.event_hash
    valid = head is not None and head.sequence == count and head.hash == previous
    return {"status": "PASS" if valid else "FAIL", "checked": count, "head_hash": previous}

import copy
from datetime import date, timedelta

from sqlalchemy import select

from rules_engine import evaluate, score_risk

from .audit import digest, record
from .errors import AppError
from .models import (
    Decision,
    Discrepancy,
    Document,
    LC,
    LCVersion,
    RuleConfig,
    Setting,
    User,
    ValidationRun,
    now,
    uid,
)
from .providers import notifications
from .security import PERMISSIONS, check_version

CHECKLIST = [
    "documents",
    "amount",
    "currency",
    "quantity",
    "dates",
    "parties",
    "shipping",
    "discrepancies",
    "risk",
    "evidence",
    "decision",
]
TRANSITIONS = {
    "SUBMIT": ({"DRAFT", "ADDITIONAL_INFORMATION_REQUIRED"}, "SUBMITTED", "LC_SUBMIT"),
    "AWAIT_DOCUMENTS": ({"SUBMITTED"}, "DOCUMENTS_PENDING", "LC_SUBMIT"),
    "START_REVIEW": (
        {"VALIDATION_COMPLETED", "DISCREPANCIES_FOUND", "ESCALATED"},
        "UNDER_REVIEW",
        "CASE_REVIEW",
    ),
    "REQUEST_INFORMATION": ({"UNDER_REVIEW"}, "ADDITIONAL_INFORMATION_REQUIRED", "CASE_REVIEW"),
    "COMPLETE_REVIEW": ({"UNDER_REVIEW"}, "REVIEW_COMPLETED", "CASE_REVIEW"),
    "REQUEST_APPROVAL": ({"REVIEW_COMPLETED"}, "PENDING_CHECKER", "CASE_REVIEW"),
    "APPROVE": ({"PENDING_CHECKER"}, "APPROVED", "CASE_APPROVE"),
    "REJECT": ({"UNDER_REVIEW", "PENDING_CHECKER", "ESCALATED"}, "REJECTED", "CASE_REJECT"),
    "ESCALATE": ({"UNDER_REVIEW", "PENDING_CHECKER", "DISCREPANCIES_FOUND"}, "ESCALATED", "CASE_ESCALATE"),
    "CLOSE": ({"APPROVED", "REJECTED"}, "CLOSED", "CASE_REVIEW"),
}
EDITABLE = {"DRAFT", "ADDITIONAL_INFORMATION_REQUIRED"}


def serialize(model, exclude=()):
    return {col.name: getattr(model, col.name) for col in model.__table__.columns if col.name not in exclude}


def sla(lc):
    if lc.status in {"APPROVED", "REJECTED", "CLOSED"}:
        return "COMPLETED"
    remaining = (lc.due_at - now()).total_seconds() / 3600
    return "BREACHED" if remaining < 0 else "AT_RISK" if remaining < 2 else "ON_TRACK"


def lc_summary(lc):
    data = serialize(lc)
    data["sla"] = sla(lc)
    data["risk_band"] = (
        "CRITICAL"
        if lc.risk_score >= 75
        else "HIGH"
        if lc.risk_score >= 45
        else "MEDIUM"
        if lc.risk_score >= 20
        else "LOW"
    )
    return data


def latest_documents(db, lc_id):
    all_docs = db.scalars(select(Document).where(Document.lc_id == lc_id).order_by(Document.version)).all()
    return list({d.type: d for d in all_docs}.values())


def snapshot(db, lc):
    return {
        "terms": lc.terms,
        "terms_version": lc.terms_version,
        "effective_date": date.today().isoformat(),
        "engine_version": "1.0",
        "documents": [
            serialize(d, ("content", "uploaded_at", "uploaded_by", "reason"))
            for d in sorted(latest_documents(db, lc.id), key=lambda d: d.type)
        ],
        "configurations": {
            r.id: {"severity": r.severity, "enabled": r.enabled, "version": r.version}
            for r in db.scalars(select(RuleConfig).order_by(RuleConfig.id))
        },
    }


def create_lc(db, user, body, correlation):
    policy = db.get(Setting, "sla_hours")
    hours = (policy.value if policy else {"STANDARD": 24, "HIGH": 8, "CRITICAL": 2})[body.priority]
    lc = LC(
        reference=f"LC-{date.today().year}-{uid()[:8].upper()}",
        title=body.title,
        priority=body.priority,
        terms=body.terms.model_dump(mode="json"),
        created_by=user.id,
        due_at=now() + timedelta(hours=hours),
    )
    db.add(lc)
    db.flush()
    db.add(LCVersion(lc_id=lc.id, version=1, terms=lc.terms, actor_id=user.id, reason="Initial creation"))
    record(db, user, "LC_CREATED", lc.id, {"reference": lc.reference, "version": 1}, correlation)
    return lc


def execute_validation(db, user, lc, correlation):
    if lc.status not in {"SUBMITTED", "DOCUMENTS_PENDING", "VALIDATION_COMPLETED", "DISCREPANCIES_FOUND"}:
        raise AppError(
            409,
            "VALIDATION_STATE",
            "Submit the case before validation; reviewed cases require an information request before changing evidence",
        )
    snap = snapshot(db, lc)
    fingerprint = digest(snap)
    existing = db.scalar(
        select(ValidationRun).where(ValidationRun.lc_id == lc.id, ValidationRun.fingerprint == fingerprint)
    )
    if existing:
        if lc.status in {"SUBMITTED", "DOCUMENTS_PENDING"}:
            lc.status = (
                "DISCREPANCIES_FOUND"
                if any(r["status"] in {"FAIL", "MANUAL_REVIEW"} for r in existing.results)
                else "VALIDATION_COMPLETED"
            )
            lc.checklist = []
            record(db, user, "VALIDATION_REUSED", lc.id, {"run_id": existing.id}, correlation)
            db.flush()
        return existing
    lc.status = "VALIDATION_IN_PROGRESS"
    record(db, user, "VALIDATION_STARTED", lc.id, {"fingerprint": fingerprint}, correlation)
    results = evaluate(snap["terms"], snap["documents"], snap["configurations"], snap["effective_date"])
    risk = score_risk(lc.terms, results, snap["documents"])
    run = ValidationRun(
        lc_id=lc.id,
        fingerprint=fingerprint,
        snapshot=snap,
        results=results,
        risk=risk,
        actor_id=user.id,
        correlation_id=correlation,
    )
    db.add(run)
    db.flush()
    for discrepancy in db.scalars(
        select(Discrepancy).where(
            Discrepancy.lc_id == lc.id, Discrepancy.status.not_in(["RESOLVED", "WAIVED", "SUPERSEDED"])
        )
    ):
        current_result = next((r for r in results if r["rule_id"] == discrepancy.rule_id), None)
        discrepancy.status = (
            "RESOLVED" if current_result and current_result["status"] == "PASS" else "SUPERSEDED"
        )
        discrepancy.resolved_at = now()
        discrepancy.decision = "Revalidated against corrected evidence; original finding preserved"
        record(
            db,
            user,
            "DISCREPANCY_REVALIDATED",
            lc.id,
            {"discrepancy_id": discrepancy.id, "status": discrepancy.status, "new_run_id": run.id},
            correlation,
        )
    for result in results:
        record(
            db,
            user,
            "RULE_EXECUTED",
            lc.id,
            {
                "run_id": run.id,
                "rule_id": result["rule_id"],
                "status": result["status"],
                "version": result["rule_version"],
            },
            correlation,
        )
        if result["status"] in {"FAIL", "MANUAL_REVIEW"}:
            discrepancy = Discrepancy(
                lc_id=lc.id,
                run_id=run.id,
                rule_id=result["rule_id"],
                severity=result["severity"],
                result=result,
            )
            db.add(discrepancy)
            db.flush()
            record(
                db,
                user,
                "DISCREPANCY_CREATED",
                lc.id,
                {"discrepancy_id": discrepancy.id, "rule_id": result["rule_id"]},
                correlation,
            )
    lc.status = (
        "DISCREPANCIES_FOUND"
        if any(r["status"] in {"FAIL", "MANUAL_REVIEW"} for r in results)
        else "VALIDATION_COMPLETED"
    )
    lc.risk_score, lc.risk_factors = risk["score"], risk["factors"]
    lc.checklist = []
    record(
        db,
        user,
        "VALIDATION_COMPLETED",
        lc.id,
        {"run_id": run.id, "risk": risk["score"], "status": lc.status},
        correlation,
    )
    notifications.send(
        db,
        lc.assigned_to or lc.created_by,
        lc.id,
        f"{lc.reference}: validation complete · {lc.status.replace('_', ' ').lower()}",
    )
    db.flush()
    return run


def latest_run(db, lc_id):
    return db.scalar(
        select(ValidationRun).where(ValidationRun.lc_id == lc_id).order_by(ValidationRun.created_at.desc())
    )


def ensure_approval_ready(db, lc):
    run = latest_run(db, lc.id)
    snap = snapshot(db, lc)
    if not run or run.fingerprint != digest(snap):
        raise AppError(
            409, "STALE_VALIDATION", "Validation must match current terms, documents, rules and today's date"
        )
    # Mandatory controls cannot be bypassed by disabling or downgrading a catalog rule.
    defaults = evaluate(lc.terms, snap["documents"], effective_date=snap["effective_date"])
    blockers = [
        r["rule_name"]
        for r in defaults
        if r["rule_id"] in {"REQUIRED_DOCUMENTS", "LC_EXPIRY", "PRESENTATION_EXPIRY"}
        and r["status"] == "FAIL"
    ]
    unresolved = db.scalars(
        select(Discrepancy).where(
            Discrepancy.run_id == run.id, Discrepancy.status.not_in(["RESOLVED", "WAIVED"])
        )
    ).all()
    if blockers or unresolved:
        raise AppError(
            409,
            "UNRESOLVED_FINDINGS",
            "Resolve or authorize all findings; missing documents and expired credits cannot be waived",
        )


def transition(db, user, lc, body, correlation):
    check_version(lc, body.version)
    spec = TRANSITIONS.get(body.action)
    if not spec or lc.status not in spec[0]:
        raise AppError(
            409, "INVALID_TRANSITION", "That workflow action is not allowed from the current state"
        )
    if spec[2] not in PERMISSIONS[user.role]:
        raise AppError(403, "PERMISSION_DENIED", "Your role cannot perform this workflow action")
    if body.action == "APPROVE":
        if user.id in {lc.created_by, lc.submitted_by, lc.reviewed_by}:
            raise AppError(
                403,
                "MAKER_CHECKER",
                "Final approval requires a checker independent of the maker and reviewer",
            )
        ensure_approval_ready(db, lc)
        if set(lc.checklist) != set(CHECKLIST):
            raise AppError(
                409, "CHECKLIST_REQUIRED", "The reviewer must complete every review checklist item"
            )
    if body.action == "COMPLETE_REVIEW":
        if user.id in {lc.created_by, lc.submitted_by}:
            raise AppError(403, "MAKER_REVIEWER", "The maker cannot complete their own review")
        if set(body.checklist) != set(CHECKLIST):
            raise AppError(422, "CHECKLIST_REQUIRED", "Complete every review checklist item")
        ensure_approval_ready(db, lc)
        lc.checklist = body.checklist
        lc.reviewed_by = user.id
    if body.action == "SUBMIT":
        lc.submitted_by = user.id
        if not lc.assigned_to:
            reviewer = db.scalar(
                select(User)
                .where(User.role == "COMPLIANCE_REVIEWER", User.active.is_(True))
                .order_by(User.email)
            )
            lc.assigned_to = reviewer.id if reviewer else None
    previous = lc.status
    lc.status = spec[1]
    db.add(
        Decision(
            lc_id=lc.id, actor_id=user.id, action=body.action, reason=body.reason, previous_state=previous
        )
    )
    record(
        db,
        user,
        body.action,
        lc.id,
        {"before": previous, "after": lc.status, "reason": body.reason, "checklist": body.checklist},
        correlation,
    )
    notifications.send(
        db, lc.assigned_to or lc.created_by, lc.id, f"{lc.reference}: {lc.status.replace('_', ' ').lower()}"
    )
    db.flush()
    return lc


def simulate(db, lc, invoice_amount):
    snap = copy.deepcopy(snapshot(db, lc))
    for document in snap["documents"]:
        if document["type"] == "COMMERCIAL_INVOICE":
            document["fields"]["amount"] = str(invoice_amount)
    results = evaluate(snap["terms"], snap["documents"], snap["configurations"], snap["effective_date"])
    return {
        "simulation": True,
        "persisted": False,
        "results": results,
        "risk": score_risk(snap["terms"], results, snap["documents"]),
        "current_risk": lc.risk_score,
    }

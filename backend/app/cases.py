import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy import String, cast, func, or_, select

from .audit import record
from .db import get_db
from .documents import MAX_FILE_SIZE, MockExtractionProvider, inspect_file
from .errors import AppError
from .ocr import recognize
from .responses import CasePage, DocumentView, LCDetailView, LCView, ValidationView
from .models import (
    AuditEvent,
    Comment,
    Decision,
    Discrepancy,
    Document,
    LC,
    LCVersion,
    User,
    ValidationRun,
    now,
)
from .schemas import Action, Assign, CreateLC, DocType, DocumentFields, EditLC, Note, Resolve, Simulation
from .security import PERMISSIONS, check_version, get_lc, require, scope
from .services import (
    CHECKLIST,
    EDITABLE,
    TRANSITIONS,
    create_lc,
    execute_validation,
    latest_run,
    lc_summary,
    serialize,
    simulate,
    transition,
)

router = APIRouter(prefix="/api/v1", tags=["LC workbench"])


@router.get("/lcs", response_model=CasePage)
@router.get("/cases", response_model=CasePage)
def list_lcs(
    q: str = Query("", max_length=150),
    status: str = Query("", max_length=40),
    priority: str = Query("", max_length=20),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    sort: str = "updated",
    user=Depends(require("LC_VIEW")),
    db=Depends(get_db),
):
    query = scope(select(LC), user)
    if q:
        pattern = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                LC.reference.ilike(pattern, escape="\\"),
                LC.title.ilike(pattern, escape="\\"),
                cast(LC.terms, String).ilike(pattern, escape="\\"),
            )
        )
    if status:
        query = query.where(LC.status == status)
    if priority:
        query = query.where(LC.priority == priority)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = {
        "updated": LC.updated_at.desc(),
        "risk": LC.risk_score.desc(),
        "due": LC.due_at,
        "reference": LC.reference,
    }.get(sort, LC.updated_at.desc())
    return {
        "items": [
            lc_summary(lc)
            for lc in db.scalars(query.order_by(order).offset((page - 1) * page_size).limit(page_size))
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/lcs", status_code=201, response_model=LCView)
def add_lc(body: CreateLC, request: Request, user=Depends(require("LC_CREATE")), db=Depends(get_db)):
    return lc_summary(create_lc(db, user, body, request.state.correlation_id))


@router.get("/lcs/{lc_id}", response_model=LCDetailView)
def detail(lc_id: str, user=Depends(require("LC_VIEW")), db=Depends(get_db)):
    lc = get_lc(db, user, lc_id)
    result = lc_summary(lc)
    permissions = PERMISSIONS[user.role]
    result["allowed_actions"] = [
        key for key, spec in TRANSITIONS.items() if lc.status in spec[0] and spec[2] in permissions
    ]
    result["review_checklist"] = CHECKLIST
    result["documents"] = (
        [
            serialize(d, ("content",))
            for d in db.scalars(
                select(Document).where(Document.lc_id == lc.id).order_by(Document.uploaded_at.desc())
            )
        ]
        if "DOCUMENT_VIEW" in permissions
        else []
    )
    run = latest_run(db, lc.id)
    result["validation"] = serialize(run, ("snapshot",)) if run else None
    result["discrepancies"] = [
        serialize(d)
        for d in db.scalars(
            select(Discrepancy).where(Discrepancy.lc_id == lc.id).order_by(Discrepancy.created_at.desc())
        )
    ]
    result["comments"] = [
        {**serialize(c), "actor_name": name}
        for c, name in db.execute(
            select(Comment, User.name)
            .join(User, Comment.actor_id == User.id)
            .where(Comment.lc_id == lc.id)
            .order_by(Comment.created_at.desc())
        )
    ]
    result["decisions"] = [
        serialize(d)
        for d in db.scalars(select(Decision).where(Decision.lc_id == lc.id).order_by(Decision.created_at))
    ]
    result["versions"] = [
        serialize(v)
        for v in db.scalars(
            select(LCVersion).where(LCVersion.lc_id == lc.id).order_by(LCVersion.version.desc())
        )
    ]
    result["audit"] = (
        [
            serialize(e)
            for e in db.scalars(
                select(AuditEvent)
                .where(AuditEvent.entity_id == lc.id)
                .order_by(AuditEvent.id.desc())
                .limit(100)
            )
        ]
        if "AUDIT_VIEW" in permissions or lc.created_by == user.id
        else []
    )
    assignee = db.get(User, lc.assigned_to) if lc.assigned_to else None
    result["assignee_name"] = assignee.name if assignee else "Unassigned"
    return result


@router.put("/lcs/{lc_id}", response_model=LCView)
def update_lc(
    lc_id: str, body: EditLC, request: Request, user=Depends(require("LC_UPDATE")), db=Depends(get_db)
):
    lc = get_lc(db, user, lc_id, True)
    check_version(lc, body.version)
    if lc.status not in EDITABLE:
        raise AppError(409, "CASE_LOCKED", "Terms can only change in draft or after an information request")
    previous = lc.terms
    lc.title, lc.priority, lc.terms = body.title, body.priority, body.terms.model_dump(mode="json")
    lc.terms_version += 1
    lc.checklist = []
    db.add(
        LCVersion(lc_id=lc.id, version=lc.terms_version, terms=lc.terms, actor_id=user.id, reason=body.reason)
    )
    record(
        db,
        user,
        "LC_UPDATED",
        lc.id,
        {"before": previous, "after": lc.terms, "reason": body.reason},
        request.state.correlation_id,
    )
    db.flush()
    return lc_summary(lc)


@router.post("/lcs/{lc_id}/workflow")
def workflow(
    lc_id: str, body: Action, request: Request, user=Depends(require("LC_VIEW")), db=Depends(get_db)
):
    return lc_summary(transition(db, user, get_lc(db, user, lc_id, True), body, request.state.correlation_id))


@router.post("/lcs/{lc_id}/assign")
def assign(
    lc_id: str, body: Assign, request: Request, user=Depends(require("CASE_ASSIGN")), db=Depends(get_db)
):
    lc = get_lc(db, user, lc_id, True)
    check_version(lc, body.version)
    assignee = db.get(User, body.user_id)
    if (
        not assignee
        or not assignee.active
        or assignee.role not in {"COMPLIANCE_REVIEWER", "SENIOR_CHECKER", "COMPLIANCE_MANAGER"}
    ):
        raise AppError(422, "INVALID_ASSIGNEE", "Select an active reviewer or checker")
    previous = lc.assigned_to
    lc.assigned_to = assignee.id
    record(
        db,
        user,
        "CASE_ASSIGNED",
        lc.id,
        {"before": previous, "after": assignee.id, "reason": body.reason},
        request.state.correlation_id,
    )
    from .providers import notifications

    notifications.send(db, assignee.id, lc.id, f"You have been assigned {lc.reference}")
    db.flush()
    return lc_summary(lc)


@router.get("/cases/assignees")
def assignees(user=Depends(require("CASE_ASSIGN")), db=Depends(get_db)):
    return [
        {"id": u.id, "name": u.name, "role": u.role}
        for u in db.scalars(
            select(User).where(
                User.active.is_(True),
                User.role.in_(["COMPLIANCE_REVIEWER", "SENIOR_CHECKER", "COMPLIANCE_MANAGER"]),
            )
        )
    ]


@router.post("/lcs/{lc_id}/comments", status_code=201)
def comment(
    lc_id: str, body: Note, request: Request, user=Depends(require("CASE_COMMENT")), db=Depends(get_db)
):
    lc = get_lc(db, user, lc_id)
    note = Comment(lc_id=lc.id, actor_id=user.id, body=body.body)
    db.add(note)
    record(db, user, "COMMENT_ADDED", lc.id, {"comment": body.body}, request.state.correlation_id)
    return {"message": "Investigation note saved"}


@router.post("/lcs/{lc_id}/documents/extract")
async def extract_document(
    lc_id: str,
    file: Annotated[UploadFile, File()],
    advanced: Annotated[bool, Form()] = False,
    user=Depends(require("DOCUMENT_CREATE")),
    db=Depends(get_db),
):
    lc = get_lc(db, user, lc_id)
    if lc.status not in EDITABLE | {"SUBMITTED", "DOCUMENTS_PENDING"}:
        raise AppError(409, "DOCUMENTS_LOCKED", "This case is locked for document changes")
    content = await file.read(MAX_FILE_SIZE + 1)
    mime, _ = inspect_file(file.filename, content)
    if mime == "application/json":
        return {
            "text": "",
            "fields": MockExtractionProvider().extract(content, mime),
            "pages": 0,
            "provider": "JSON",
            "review_required": True,
        }
    if advanced:
        return await recognize(content, file.filename, mime, advanced=True)
    return await recognize(content, file.filename, mime)


@router.post("/lcs/{lc_id}/documents", status_code=201, response_model=DocumentView)
async def upload(
    lc_id: str,
    request: Request,
    type: Annotated[DocType, Form()],
    version: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    fields: Annotated[str, Form()] = "",
    reason: Annotated[str, Form()] = "Initial document submission",
    user=Depends(require("DOCUMENT_CREATE")),
    db=Depends(get_db),
):
    lc = get_lc(db, user, lc_id, True)
    check_version(lc, version)
    if lc.status not in EDITABLE | {"SUBMITTED", "DOCUMENTS_PENDING"}:
        raise AppError(
            409, "DOCUMENTS_LOCKED", "Request additional information before changing validated evidence"
        )
    if not 10 <= len(reason.strip()) <= 1000:
        raise AppError(
            422, "REASON_REQUIRED", "A 10–1000 character submission or replacement reason is required"
        )
    content = await file.read(MAX_FILE_SIZE + 1)
    mime, hashed = inspect_file(file.filename, content)
    if db.scalar(select(Document).where(Document.lc_id == lc.id, Document.sha256 == hashed)):
        raise AppError(409, "DUPLICATE_DOCUMENT", "These exact file bytes already exist in this case")
    try:
        extracted = (
            DocumentFields.model_validate(json.loads(fields)).model_dump(mode="json")
            if fields
            else MockExtractionProvider().extract(content, mime)
        )
    except ValueError:
        raise AppError(
            422, "INVALID_DOCUMENT_FIELDS", "Document fields do not match the required schema"
        ) from None
    if not extracted:
        raise AppError(
            422,
            "MANUAL_FIELDS_REQUIRED",
            "Extract the document with OCR and review its fields before uploading, or enter fields manually",
        )
    previous = db.scalar(
        select(Document)
        .where(Document.lc_id == lc.id, Document.type == type)
        .order_by(Document.version.desc())
    )
    document = Document(
        lc_id=lc.id,
        type=type,
        number=extracted["number"],
        version=previous.version + 1 if previous else 1,
        filename=file.filename,
        sha256=hashed,
        mime=mime,
        size=len(content),
        content=content,
        fields=extracted,
        uploaded_by=user.id,
        reason=reason,
    )
    db.add(document)
    lc.updated_at = now()
    lc.checklist = []
    db.flush()
    record(
        db,
        user,
        "DOCUMENT_REPLACED" if previous else "DOCUMENT_UPLOADED",
        lc.id,
        {
            "document_id": document.id,
            "previous_document": previous.id if previous else None,
            "sha256": hashed,
            "version": document.version,
            "reason": reason,
        },
        request.state.correlation_id,
    )
    return serialize(document, ("content",))


@router.get("/documents/{document_id}/download")
def download(document_id: str, request: Request, user=Depends(require("DOCUMENT_VIEW")), db=Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise AppError(404, "NOT_FOUND", "Document not found")
    get_lc(db, user, document.lc_id)
    record(
        db,
        user,
        "DOCUMENT_DOWNLOADED",
        document.lc_id,
        {"document_id": document.id},
        request.state.correlation_id,
    )
    suffix = {"application/json": "json", "application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[
        document.mime
    ]
    return Response(
        document.content,
        media_type=document.mime,
        headers={
            "Content-Disposition": f'attachment; filename="{document.id}.{suffix}"',
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post("/lcs/{lc_id}/validation", response_model=ValidationView)
def validate(lc_id: str, request: Request, user=Depends(require("VALIDATION_RUN")), db=Depends(get_db)):
    return serialize(
        execute_validation(db, user, get_lc(db, user, lc_id, True), request.state.correlation_id),
        ("snapshot",),
    )


@router.get("/validation/{run_id}")
def get_validation(run_id: str, user=Depends(require("LC_VIEW")), db=Depends(get_db)):
    run = db.get(ValidationRun, run_id)
    if not run:
        raise AppError(404, "NOT_FOUND", "Validation run not found")
    get_lc(db, user, run.lc_id)
    return serialize(run)


@router.post("/lcs/{lc_id}/simulate")
def simulation(lc_id: str, body: Simulation, user=Depends(require("RULE_VIEW")), db=Depends(get_db)):
    if "LC_VIEW" not in PERMISSIONS[user.role]:
        raise AppError(403, "PERMISSION_DENIED", "Business data access required")
    return simulate(db, get_lc(db, user, lc_id), body.invoice_amount)


@router.get("/discrepancies")
def discrepancies(page: int = Query(1, ge=1), user=Depends(require("LC_VIEW")), db=Depends(get_db)):
    accessible = scope(select(LC.id), user)
    query = select(Discrepancy).where(Discrepancy.lc_id.in_(accessible))
    return {
        "items": [
            serialize(d)
            for d in db.scalars(
                query.order_by(Discrepancy.created_at.desc()).offset((page - 1) * 25).limit(25)
            )
        ],
        "total": db.scalar(select(func.count()).select_from(query.subquery())),
    }


@router.patch("/discrepancies/{discrepancy_id}")
def resolve(
    discrepancy_id: str,
    body: Resolve,
    request: Request,
    user=Depends(require("CASE_REVIEW")),
    db=Depends(get_db),
):
    finding = db.get(Discrepancy, discrepancy_id)
    if not finding:
        raise AppError(404, "NOT_FOUND", "Finding not found")
    lc = get_lc(db, user, finding.lc_id, True)
    check_version(lc, body.version)
    run = latest_run(db, lc.id)
    if (
        lc.status != "UNDER_REVIEW"
        or not run
        or finding.run_id != run.id
        or finding.status in {"SUPERSEDED", "RESOLVED"}
    ):
        raise AppError(
            409, "FINDING_LOCKED", "Only current findings in an active review can receive a decision"
        )
    if body.status == "WAIVED":
        if "CASE_OVERRIDE" not in PERMISSIONS[user.role]:
            raise AppError(403, "OVERRIDE_DENIED", "An authorized manager or checker must justify a waiver")
        if user.id in {lc.created_by, lc.submitted_by}:
            raise AppError(403, "MAKER_CHECKER", "Makers cannot waive their own findings")
        if finding.severity == "CRITICAL" or finding.rule_id in {
            "REQUIRED_DOCUMENTS",
            "LC_EXPIRY",
            "PRESENTATION_EXPIRY",
        }:
            raise AppError(
                409, "NON_WAIVABLE", "Critical findings require corrected evidence, not an override"
            )
    previous = finding.status
    finding.status, finding.decision, finding.decided_by = body.status, body.reason, user.id
    finding.resolved_at = now() if body.status in {"WAIVED", "REJECTED"} else None
    lc.updated_at = now()
    lc.checklist = []
    record(
        db,
        user,
        "OVERRIDE_CREATED" if body.status == "WAIVED" else "DISCREPANCY_UPDATED",
        lc.id,
        {
            "discrepancy_id": finding.id,
            "before": previous,
            "after": body.status,
            "reason": body.reason,
            "system_result": finding.result,
        },
        request.state.correlation_id,
    )
    return serialize(finding)

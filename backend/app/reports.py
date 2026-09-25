import csv
import io
from collections import Counter
from datetime import timedelta
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Query, Request, Response
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import func, select

from .audit import record
from .config import DISCLAIMER
from .db import get_db
from .models import AuditEvent, Decision, Discrepancy, LC, now
from .security import get_lc, require, scope
from .services import latest_documents, latest_run, lc_summary, serialize, sla

router = APIRouter(prefix="/api/v1/reports", tags=["Reporting"])


@router.get("/dashboard")
def dashboard(user=Depends(require("REPORT_VIEW")), db=Depends(get_db)):
    lcs = db.scalars(scope(select(LC), user)).all()
    ids = [lc.id for lc in lcs]
    findings = (
        db.scalars(
            select(Discrepancy).where(Discrepancy.lc_id.in_(ids), Discrepancy.status != "SUPERSEDED")
        ).all()
        if ids
        else []
    )
    closed = [lc for lc in lcs if lc.status in {"APPROVED", "REJECTED", "CLOSED"}]
    open_cases = [lc for lc in lcs if lc not in closed]
    trend = []
    for offset in reversed(range(7)):
        day = (now() - timedelta(days=offset)).date()
        daily = [lc for lc in lcs if lc.created_at.date() == day]
        trend.append(
            {
                "date": day.isoformat(),
                "label": day.strftime("%a"),
                "cases": len(daily),
                "flagged": sum(lc.risk_score >= 45 for lc in daily),
            }
        )
    return {
        "total": len(lcs),
        "open": len(open_cases),
        "pending_review": sum(
            lc.status in {"UNDER_REVIEW", "PENDING_CHECKER", "DISCREPANCIES_FOUND"} for lc in lcs
        ),
        "approved": sum(lc.status == "APPROVED" for lc in lcs),
        "high_risk": sum(lc.risk_score >= 45 for lc in lcs),
        "sla_breaches": sum(sla(lc) == "BREACHED" for lc in lcs),
        "average_hours": round(
            sum((lc.updated_at - lc.created_at).total_seconds() / 3600 for lc in closed) / len(closed), 1
        )
        if closed
        else 0,
        "approval_rate": round(sum(lc.status == "APPROVED" for lc in lcs) / len(closed) * 100, 1)
        if closed
        else 0,
        "discrepancies": len(findings),
        "overrides": sum(d.status == "WAIVED" for d in findings),
        "currencies": dict(Counter(lc.terms["currency"] for lc in lcs)),
        "status_distribution": dict(Counter(lc.status for lc in lcs)),
        "risk_distribution": dict(Counter(lc_summary(lc)["risk_band"] for lc in lcs)),
        "sla_distribution": dict(Counter(sla(lc) for lc in lcs)),
        "discrepancy_categories": dict(Counter(d.result["category"] for d in findings)),
        "rule_failures": dict(Counter(d.rule_id for d in findings)),
        "trend": trend,
        "attention": [
            lc_summary(lc) for lc in sorted(open_cases, key=lambda lc: (-lc.risk_score, lc.due_at))[:5]
        ],
        "recent": [lc_summary(lc) for lc in sorted(lcs, key=lambda lc: lc.updated_at, reverse=True)[:6]],
        "disclaimer": DISCLAIMER,
        "generated_at": now(),
    }


def csv_safe(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value


@router.get("/export")
def export(
    request: Request,
    format: str = Query("csv", pattern="^(csv|json)$"),
    user=Depends(require("EXPORT_DATA")),
    db=Depends(get_db),
):
    lcs = db.scalars(scope(select(LC), user).order_by(LC.created_at.desc()).limit(1000)).all()
    record(
        db,
        user,
        "DATA_EXPORTED",
        "cases",
        {"format": format, "rows": len(lcs), "maximum": 1000},
        request.state.correlation_id,
    )
    if format == "json":
        return {"disclaimer": DISCLAIMER, "items": [lc_summary(lc) for lc in lcs]}
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([DISCLAIMER])
    writer.writerow(
        ["Reference", "Title", "Applicant", "Beneficiary", "Currency", "Amount", "Status", "Risk", "SLA"]
    )
    for lc in lcs:
        writer.writerow(
            map(
                csv_safe,
                [
                    lc.reference,
                    lc.title,
                    lc.terms["applicant"],
                    lc.terms["beneficiary"],
                    lc.terms["currency"],
                    lc.terms["amount"],
                    lc.status,
                    lc.risk_score,
                    sla(lc),
                ],
            )
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="lc-verify-cases.csv"'},
    )


@router.get("/lcs/{lc_id}")
def compliance_report(
    lc_id: str,
    request: Request,
    format: str = Query("json", pattern="^(json|pdf)$"),
    user=Depends(require("EXPORT_DATA")),
    db=Depends(get_db),
):
    lc = get_lc(db, user, lc_id)
    run = latest_run(db, lc.id)
    report = {
        "report_id": f"RPT-{lc.reference}-{lc.version}",
        "generated_at": now(),
        "disclaimer": DISCLAIMER,
        "case": lc_summary(lc),
        "documents": [serialize(d, ("content",)) for d in latest_documents(db, lc.id)],
        "validation": serialize(run, ("snapshot",)) if run else None,
        "discrepancies": [
            serialize(d) for d in db.scalars(select(Discrepancy).where(Discrepancy.lc_id == lc.id))
        ],
        "approvals": [serialize(d) for d in db.scalars(select(Decision).where(Decision.lc_id == lc.id))],
        "audit_event_count": db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.entity_id == lc.id)
        ),
    }
    record(
        db,
        user,
        "COMPLIANCE_REPORT_EXPORTED",
        lc.id,
        {"format": format, "report_id": report["report_id"]},
        request.state.correlation_id,
    )
    if format == "json":
        return report
    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#0b3443")
    parts = []

    def line(value, style="BodyText"):
        parts.append(Paragraph(escape(str(value)), styles[style]))
        parts.append(Spacer(1, 7))

    line("LC-VERIFY / COMPLIANCE REPORT", "Title")
    line(DISCLAIMER)
    line(f"{report['report_id']} · Generated {now().isoformat()} UTC")
    line(f"{lc.reference} — {lc.title}", "Heading1")
    line(f"Status: {lc.status} | Risk: {lc.risk_score}/100 | SLA: {sla(lc)}")
    line("LC terms", "Heading2")
    for key, value in lc.terms.items():
        line(f"{key.replace('_', ' ').title()}: {value}")
    line("Document evidence", "Heading2")
    for d in report["documents"]:
        line(f"{d['type']} / {d['number']} / version {d['version']} / SHA-256 {d['sha256']}")
    line("Validation results", "Heading2")
    for result in run.results if run else []:
        line(f"{result['rule_name']} — {result['status']} ({result['severity']})", "Heading3")
        line(f"Expected: {result['expected_value']} | Actual: {result['actual_value']}")
        line(result["explanation"])
    line("Human decisions and overrides", "Heading2")
    for d in report["discrepancies"]:
        line(f"{d['rule_id']}: {d['status']} — {d['decision'] or 'No human decision'}")
    for d in report["approvals"]:
        line(f"{d['action']} by {d['actor_id']} at {d['created_at']}: {d['reason']}")
    line("Risk factors", "Heading2")
    for factor in lc.risk_factors:
        line(f"+{factor['points']}: {factor['label']}")
    line(f"Audit events linked to case: {report['audit_event_count']}")
    line(
        "Simplified synthetic trade-finance consistency validation. Not a substitute for bank policy, legal advice or official ICC/UCP interpretation."
    )

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(40, 25, f"LC-VERIFY | Synthetic demonstration | Page {doc.page}")

    SimpleDocTemplate(stream, rightMargin=45, leftMargin=45, topMargin=40, bottomMargin=45).build(
        parts, onFirstPage=footer, onLaterPages=footer
    )
    return Response(
        stream.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{lc.reference}-compliance.pdf"'},
    )

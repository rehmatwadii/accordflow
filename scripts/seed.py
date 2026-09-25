"""Idempotent, demo-only synthetic seed. Password generated locally and never committed."""

import json
import os
import secrets
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

from backend.app.audit import record
from backend.app.config import ENV
from backend.app.db import SessionLocal
from backend.app.models import AuditHead, Document, LC, RuleConfig, Setting, User, now
from backend.app.schemas import CreateLC, Terms
from backend.app.security import hasher, password_valid
from backend.app.services import create_lc, execute_validation
from rules_engine import CATALOG

ACCOUNTS = [
    ("analyst", "Avery Morgan", "TRADE_ANALYST"),
    ("reviewer", "Jordan Chen", "COMPLIANCE_REVIEWER"),
    ("checker", "Samira Khan", "SENIOR_CHECKER"),
    ("manager", "Alex Bennett", "COMPLIANCE_MANAGER"),
    ("auditor", "Taylor Reed", "INTERNAL_AUDITOR"),
    ("executive", "Cameron Ellis", "EXECUTIVE_VIEWER"),
    ("admin", "Morgan Blake", "SYSTEM_ADMIN"),
]


def demo_terms(index=0):
    today = date.today()
    quantity = 100 + index * 10
    return Terms(
        applicant=[
            "Atlas Textiles Limited",
            "Northstar Trading Company",
            "Crescent Industrial Limited",
            "Bluewater Imports Limited",
        ][index % 4],
        beneficiary=[
            "Straits Supply Limited",
            "Pacific Looms Limited",
            "Alpine Components Limited",
            "Harbor Commodities Limited",
        ][index % 4],
        amount=str(quantity * 1250),
        issue_date=today - timedelta(days=12),
        expiry_date=today + timedelta(days=30),
        latest_shipment=today - timedelta(days=2),
        presentation_date=today,
        loading_port="Singapore",
        discharge_port="Port Qasim",
        goods=[
            "Premium woven cotton fabric",
            "Industrial weaving machinery",
            "Precision machine components",
            "Raw cotton, grade A",
        ][index % 4],
        quantity=str(quantity),
        unit_price="1250",
        incoterm="FOB",
    ).model_dump(mode="json")


def demo_documents(terms, scenario="perfect"):
    base = {"issue_date": (date.today() - timedelta(days=3)).isoformat()}
    invoice = {
        **base,
        "number": "SYN-INV-001",
        "amount": terms["amount"],
        "currency": terms["currency"],
        "quantity": terms["quantity"],
        "unit_price": terms["unit_price"],
        "quantity_unit": terms["quantity_unit"],
        "applicant": terms["applicant"],
        "beneficiary": terms["beneficiary"],
        "incoterm": terms["incoterm"],
        "line_totals": [terms["amount"]],
    }
    shipping = {
        **base,
        "number": "SYN-BL-001",
        "quantity": terms["quantity"],
        "quantity_unit": terms["quantity_unit"],
        "shipment_date": (date.today() - timedelta(days=3)).isoformat(),
        "loading_port": terms["loading_port"],
        "discharge_port": terms["discharge_port"],
        "consignee": terms["applicant"],
        "notify_party": terms["applicant"],
        "vessel": "MV Synthetic Horizon",
        "partial_shipment": False,
        "transshipment": False,
    }
    packing = {
        **base,
        "number": "SYN-PK-001",
        "quantity": terms["quantity"],
        "quantity_unit": terms["quantity_unit"],
    }
    origin = {**base, "number": "SYN-CO-001", "country": terms["beneficiary_country"]}
    if scenario in {"amount", "multiple", "override"}:
        invoice["amount"] = str(int(terms["amount"]) * 1.08)
        invoice["unit_price"] = "1350"
        invoice["line_totals"] = [invoice["amount"]]
    if scenario in {"late", "multiple"}:
        shipping["shipment_date"] = (date.today() - timedelta(days=1)).isoformat()
    if scenario in {"quantity", "multiple"}:
        packing["quantity"] = str(int(terms["quantity"]) - 5)
    docs = [
        {"type": t, "fields": f}
        for t, f in [
            ("COMMERCIAL_INVOICE", invoice),
            ("BILL_OF_LADING", shipping),
            ("PACKING_LIST", packing),
            ("CERTIFICATE_OF_ORIGIN", origin),
        ]
    ]
    if scenario == "missing":
        docs = [d for d in docs if d["type"] != "CERTIFICATE_OF_ORIGIN"]
    if scenario == "multiple":
        invoice["currency"] = "EUR"
    return docs


def initialize(db, password):
    if not db.get(AuditHead, 1):
        db.add(AuditHead(id=1, sequence=0, hash="0" * 64))
    for rule in CATALOG:
        if not db.get(RuleConfig, rule[0]):
            db.add(RuleConfig(id=rule[0], severity=rule[3], enabled=True))
    if not db.get(Setting, "sla_hours"):
        db.add(Setting(key="sla_hours", value={"STANDARD": 24, "HIGH": 8, "CRITICAL": 2}))
        db.add(
            Setting(
                key="retention",
                value={
                    "audit": "Indefinite in demo; no automatic deletion",
                    "documents_days": 365,
                    "policy": "Synthetic demo only; legal review required before production",
                },
            )
        )
    users = {}
    password_valid(password)
    for slug, name, role in ACCOUNTS:
        user = db.scalar(select(User).where(User.email == f"{slug}@lcverify.demo"))
        if not user:
            user = User(
                email=f"{slug}@lcverify.demo", name=name, role=role, password_hash=hasher.hash(password)
            )
            db.add(user)
            db.flush()
        users[slug] = user
    db.flush()
    return users


def seed():
    if ENV not in {"demo", "development", "test"}:
        raise RuntimeError("Synthetic seeding is prohibited outside demo/development/test")
    credentials_path = Path(".demo-credentials.json")
    previous = json.loads(credentials_path.read_text()) if credentials_path.exists() else {}
    password = (
        os.getenv("DEMO_PASSWORD") or previous.get("password") or "Demo-" + secrets.token_urlsafe(18) + "7aA"
    )
    with SessionLocal() as db:
        users = initialize(db, password)
        if db.scalar(select(LC).limit(1)):
            print("Demo database already seeded; existing records preserved.")
            return
        scenarios = [
            "multiple",
            "perfect",
            "amount",
            "late",
            "missing",
            "quantity",
            "perfect",
            "override",
            "perfect",
            "amount",
            "perfect",
            "perfect",
            "perfect",
            "missing",
            "late",
            "multiple",
        ]
        for i, scenario in enumerate(scenarios):
            terms = demo_terms(i)
            lc = create_lc(
                db,
                users["analyst"],
                CreateLC(
                    title=terms["goods"],
                    priority="HIGH" if i % 3 == 0 else "STANDARD",
                    terms=Terms.model_validate(terms),
                ),
                "SEED",
            )
            lc.reference = f"LC-{date.today().year}-{1042 + i:05}"
            lc.created_at = now() - timedelta(days=i % 7, hours=i)
            lc.due_at = now() + timedelta(hours=[-3, 18, 1, 5, 12, 30][i % 6])
            lc.assigned_to = users["reviewer"].id
            if i < 13:
                from backend.app.documents import inspect_file

                for d in demo_documents(terms, scenario):
                    content = json.dumps(d["fields"]).encode()
                    filename = d["type"].lower() + ".json"
                    mime, sha = inspect_file(filename, content)
                    db.add(
                        Document(
                            lc_id=lc.id,
                            type=d["type"],
                            number=d["fields"]["number"],
                            version=1,
                            filename=filename,
                            sha256=sha,
                            mime=mime,
                            size=len(content),
                            content=content,
                            fields=d["fields"],
                            uploaded_by=users["analyst"].id,
                        )
                    )
                lc.status = "SUBMITTED"
                lc.submitted_by = users["analyst"].id
                db.flush()
                execute_validation(db, users["analyst"], lc, "SEED")
                if i in {1, 6, 8}:
                    from backend.app.schemas import Action
                    from backend.app.services import CHECKLIST, transition

                    for action in ["START_REVIEW", "COMPLETE_REVIEW", "REQUEST_APPROVAL"]:
                        transition(
                            db,
                            users["reviewer"],
                            lc,
                            Action(
                                action=action,
                                version=lc.version,
                                reason="Synthetic demonstration review completed",
                                checklist=CHECKLIST,
                            ),
                            "SEED",
                        )
                    if i != 8:
                        transition(
                            db,
                            users["checker"],
                            lc,
                            Action(
                                action="APPROVE",
                                version=lc.version,
                                reason="Independent synthetic checker approval",
                            ),
                            "SEED",
                        )
            record(db, users["admin"], "SYNTHETIC_SCENARIO_SEEDED", lc.id, {"scenario": scenario}, "SEED")
        db.commit()
    credentials_path.write_text(
        json.dumps(
            {
                "warning": "LOCAL DEMO ONLY — DO NOT COMMIT",
                "password": password,
                "accounts": [f"{a[0]}@lcverify.demo" for a in ACCOUNTS],
            },
            indent=2,
        )
    )
    print("Seeded 16 synthetic cases and 7 demo roles. Credentials saved in .demo-credentials.json")


if __name__ == "__main__":
    seed()

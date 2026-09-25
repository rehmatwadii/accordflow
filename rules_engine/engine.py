"""Deterministic, decimal-safe synthetic documentary consistency rules, version 1.0."""

import re
import unicodedata
from datetime import date
from decimal import Decimal

CATALOG = [
    (
        "REQUIRED_DOCUMENTS",
        "Required documents",
        "Documents",
        "CRITICAL",
        "Every document required by the LC/profile must be present.",
    ),
    (
        "AMOUNT_TOLERANCE",
        "Invoice amount tolerance",
        "Amount",
        "HIGH",
        "Invoice must not exceed LC plus percentage and absolute tolerance.",
    ),
    ("CURRENCY_MATCH", "Currency consistency", "Amount", "HIGH", "Invoice and LC currencies must match."),
    (
        "INVOICE_ARITHMETIC",
        "Invoice arithmetic",
        "Amount",
        "HIGH",
        "Quantity × unit price must equal invoice amount to 0.01.",
    ),
    (
        "LINE_TOTALS",
        "Invoice line totals",
        "Amount",
        "HIGH",
        "Sum of supplied line totals must equal invoice amount.",
    ),
    (
        "LC_EXPIRY",
        "Credit expiry",
        "Dates",
        "CRITICAL",
        "The effective validation date must be on or before LC expiry.",
    ),
    (
        "SHIPMENT_DATE",
        "Latest shipment date",
        "Dates",
        "HIGH",
        "Shipment must occur on or before the last permitted date.",
    ),
    (
        "PRESENTATION_EXPIRY",
        "Presentation before expiry",
        "Dates",
        "CRITICAL",
        "Presentation must occur on or before expiry.",
    ),
    (
        "PRESENTATION_PERIOD",
        "Presentation period",
        "Dates",
        "HIGH",
        "Presentation must follow shipment within the permitted days.",
    ),
    (
        "DOCUMENT_DATES",
        "Document date sequence",
        "Dates",
        "MEDIUM",
        "Documents must be dated between issuance and presentation.",
    ),
    (
        "QUANTITY_MATCH",
        "Cross-document quantities",
        "Quantity",
        "MEDIUM",
        "Invoice, packing and shipping quantities must match LC quantity.",
    ),
    (
        "QUANTITY_UNIT",
        "Quantity unit consistency",
        "Quantity",
        "MEDIUM",
        "Document quantity units must match LC units.",
    ),
    (
        "PARTY_MATCH",
        "Applicant and beneficiary",
        "Parties",
        "HIGH",
        "Party normalization may ignore punctuation and legal suffix spelling only.",
    ),
    (
        "CONSIGNEE_MATCH",
        "Consignee and notify party",
        "Parties",
        "HIGH",
        "Transport consignee and notify party must match the applicant in this demo policy.",
    ),
    ("PORT_MATCH", "Loading and discharge ports", "Shipping", "HIGH", "Transport ports must match LC ports."),
    (
        "SHIPMENT_POLICY",
        "Shipment permissions",
        "Shipping",
        "HIGH",
        "Partial shipment and transshipment must be permitted by LC terms.",
    ),
    (
        "TRANSPORT_REFERENCE",
        "Transport reference",
        "Shipping",
        "MEDIUM",
        "A transport document requires a vessel or transport reference.",
    ),
    ("INCOTERM_MATCH", "Incoterm consistency", "Shipping", "MEDIUM", "Invoice Incoterm must match the LC."),
    (
        "ORIGIN_COUNTRY",
        "Country of origin",
        "Parties",
        "MEDIUM",
        "Origin certificate must match the configured beneficiary country.",
    ),
    (
        "INSURANCE_COVER",
        "Insurance coverage",
        "Documents",
        "HIGH",
        "For CIF/CIP or insurance profiles require coverage of at least 110% of invoice.",
    ),
]


def normalize(value):
    words = re.findall(r"\w+", unicodedata.normalize("NFKC", str(value or "")).casefold())
    return " ".join({"ltd": "limited", "co": "company", "corp": "corporation"}.get(w, w) for w in words)


def decimal(value):
    return Decimal(str(value)) if value is not None else Decimal("0")


def evaluate(
    terms: dict, documents: list[dict], configurations: dict | None = None, effective_date: str | None = None
):
    configurations = configurations or {}
    docs = {d["type"]: d for d in documents}
    inv = docs.get("COMMERCIAL_INVOICE", {}).get("fields", {})
    bl = docs.get("BILL_OF_LADING", {}).get("fields", {})
    day = date.fromisoformat(effective_date) if effective_date else date.today()
    results = []

    def add(rule_id, ok, expected, actual, evidence_types=(), manual=False, warning=False):
        meta = next(r for r in CATALOG if r[0] == rule_id)
        config = configurations.get(rule_id, {"severity": meta[3], "enabled": True, "version": 1})
        status = (
            "NOT_APPLICABLE"
            if not config["enabled"] or ok is None
            else "MANUAL_REVIEW"
            if manual
            else "WARNING"
            if warning
            else "PASS"
            if ok
            else "FAIL"
        )
        results.append(
            {
                "rule_id": rule_id,
                "rule_name": meta[1],
                "category": meta[2],
                "severity": config["severity"],
                "rule_version": config["version"],
                "engine_version": "1.0",
                "status": status,
                "expected_value": str(expected),
                "actual_value": str(actual),
                "explanation": meta[4] + (" Normalized Match." if warning else ""),
                "evidence": [
                    {
                        "document_id": docs[t].get("id"),
                        "type": t,
                        "version": docs[t].get("version", 1),
                        "number": docs[t]["fields"].get("number"),
                    }
                    for t in evidence_types
                    if t in docs
                ],
                "recommendation": "No action required."
                if status == "PASS"
                else "Review the source evidence and LC terms; correct inputs or record an authorized decision.",
            }
        )

    required = set(terms["required_documents"])
    if terms["incoterm"] in {"CIF", "CIP"} or terms["rule_profile"] == "INSURANCE_REQUIRED":
        required.add("INSURANCE_CERTIFICATE")
    missing = sorted(required - set(docs))
    add(
        "REQUIRED_DOCUMENTS",
        not missing,
        ", ".join(sorted(required)),
        "All present" if not missing else "Missing: " + ", ".join(missing),
        required,
    )
    maximum = decimal(terms["amount"]) * (1 + decimal(terms["tolerance_pct"]) / 100) + decimal(
        terms["tolerance_amount"]
    )
    add(
        "AMOUNT_TOLERANCE",
        bool(inv.get("amount")) and decimal(inv.get("amount")) <= maximum,
        f"≤ {maximum}",
        inv.get("amount", "Missing"),
        ["COMMERCIAL_INVOICE"],
    )
    add(
        "CURRENCY_MATCH",
        bool(inv.get("currency")) and inv.get("currency") == terms["currency"],
        terms["currency"],
        inv.get("currency", "Missing"),
        ["COMMERCIAL_INVOICE"],
    )
    calculated = (decimal(inv.get("quantity")) * decimal(inv.get("unit_price"))).quantize(Decimal("0.01"))
    add(
        "INVOICE_ARITHMETIC",
        bool(inv.get("quantity"))
        and bool(inv.get("unit_price"))
        and calculated == decimal(inv.get("amount")),
        calculated,
        inv.get("amount", "Missing"),
        ["COMMERCIAL_INVOICE"],
    )
    add(
        "LINE_TOTALS",
        sum(map(decimal, inv.get("line_totals", []))) == decimal(inv.get("amount"))
        if inv.get("line_totals")
        else None,
        inv.get("amount"),
        sum(map(decimal, inv.get("line_totals", []))),
        ["COMMERCIAL_INVOICE"],
    )
    add("LC_EXPIRY", day <= date.fromisoformat(terms["expiry_date"]), terms["expiry_date"], day)
    shipment = date.fromisoformat(bl["shipment_date"]) if bl.get("shipment_date") else None
    presentation = date.fromisoformat(terms["presentation_date"])
    add(
        "SHIPMENT_DATE",
        shipment is not None
        and date.fromisoformat(terms["issue_date"])
        <= shipment
        <= date.fromisoformat(terms["latest_shipment"]),
        terms["latest_shipment"],
        shipment or "Missing",
        ["BILL_OF_LADING"],
    )
    add(
        "PRESENTATION_EXPIRY",
        presentation <= date.fromisoformat(terms["expiry_date"]),
        terms["expiry_date"],
        presentation,
    )
    elapsed = (presentation - shipment).days if shipment else None
    add(
        "PRESENTATION_PERIOD",
        elapsed is not None and 0 <= elapsed <= terms["presentation_period"],
        f"0–{terms['presentation_period']} days",
        elapsed,
        ["BILL_OF_LADING"],
    )
    invalid_dates = [
        d["type"]
        for d in documents
        if not terms["issue_date"] <= d["fields"].get("issue_date", "") <= terms["presentation_date"]
    ]
    add(
        "DOCUMENT_DATES",
        not invalid_dates and bool(documents),
        "Issue ≤ document date ≤ presentation",
        invalid_dates or "Valid dates",
        docs,
    )
    quantitative = ["COMMERCIAL_INVOICE", "PACKING_LIST", "BILL_OF_LADING"]
    quantities = {t: docs.get(t, {}).get("fields", {}).get("quantity") for t in quantitative}
    units = {t: docs.get(t, {}).get("fields", {}).get("quantity_unit") for t in quantitative}
    add(
        "QUANTITY_MATCH",
        all(v is not None and decimal(v) == decimal(terms["quantity"]) for v in quantities.values()),
        terms["quantity"],
        quantities,
        quantitative,
    )
    add(
        "QUANTITY_UNIT",
        all(normalize(v) == normalize(terms["quantity_unit"]) for v in units.values()),
        terms["quantity_unit"],
        units,
        quantitative,
    )
    parties_ok = all(normalize(inv.get(k)) == normalize(terms[k]) for k in ("applicant", "beneficiary"))
    add(
        "PARTY_MATCH",
        parties_ok,
        f"{terms['applicant']} / {terms['beneficiary']}",
        f"{inv.get('applicant')} / {inv.get('beneficiary')}",
        ["COMMERCIAL_INVOICE"],
        warning=parties_ok and any(inv.get(k) != terms[k] for k in ("applicant", "beneficiary")),
    )
    add(
        "CONSIGNEE_MATCH",
        all(normalize(bl.get(k)) == normalize(terms["applicant"]) for k in ("consignee", "notify_party")),
        terms["applicant"],
        f"{bl.get('consignee')} / {bl.get('notify_party')}",
        ["BILL_OF_LADING"],
    )
    add(
        "PORT_MATCH",
        all(normalize(bl.get(k)) == normalize(terms[k]) for k in ("loading_port", "discharge_port")),
        f"{terms['loading_port']} → {terms['discharge_port']}",
        f"{bl.get('loading_port')} → {bl.get('discharge_port')}",
        ["BILL_OF_LADING"],
    )
    add(
        "SHIPMENT_POLICY",
        bool(bl) and all(not bl.get(k) or terms[k] for k in ("partial_shipment", "transshipment")),
        f"Partial {terms['partial_shipment']}; transshipment {terms['transshipment']}",
        f"Partial {bl.get('partial_shipment')}; transshipment {bl.get('transshipment')}",
        ["BILL_OF_LADING"],
    )
    add(
        "TRANSPORT_REFERENCE",
        bool(bl.get("vessel")),
        "Vessel / transport reference",
        bl.get("vessel", "Missing"),
        ["BILL_OF_LADING"],
    )
    add(
        "INCOTERM_MATCH",
        inv.get("incoterm") == terms["incoterm"],
        terms["incoterm"],
        inv.get("incoterm", "Missing"),
        ["COMMERCIAL_INVOICE"],
    )
    origin = docs.get("CERTIFICATE_OF_ORIGIN", {}).get("fields", {}).get("country")
    add(
        "ORIGIN_COUNTRY",
        normalize(origin) == normalize(terms["beneficiary_country"])
        if "CERTIFICATE_OF_ORIGIN" in required or origin
        else None,
        terms["beneficiary_country"],
        origin,
        ["CERTIFICATE_OF_ORIGIN"],
    )
    cover = docs.get("INSURANCE_CERTIFICATE", {}).get("fields", {})
    add(
        "INSURANCE_COVER",
        decimal(cover.get("amount")) >= decimal(inv.get("amount")) * Decimal("1.1")
        and cover.get("currency") == terms["currency"]
        if "INSURANCE_CERTIFICATE" in required
        else None,
        decimal(inv.get("amount")) * Decimal("1.1"),
        cover.get("amount", "Missing"),
        ["INSURANCE_CERTIFICATE"],
    )
    return results


def score_risk(terms, results, documents=None):
    weights = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8, "LOW": 3, "INFO": 1}
    factors = [
        {"label": r["rule_name"], "points": weights[r["severity"]], "rule_id": r["rule_id"]}
        for r in results
        if r["status"] in {"FAIL", "MANUAL_REVIEW"}
    ]
    if decimal(terms["amount"]) >= 1000000:
        factors.append({"label": "High-value credit (≥ 1M nominal currency units)", "points": 10})
    if any(d.get("version", 1) >= 3 for d in documents or []):
        factors.append({"label": "Repeated document resubmission", "points": 5})
    score = min(100, sum(f["points"] for f in factors))
    return {
        "score": score,
        "band": "CRITICAL" if score >= 75 else "HIGH" if score >= 45 else "MEDIUM" if score >= 20 else "LOW",
        "factors": factors,
        "explanation": "Weighted synthetic policy; factors sum to an uncapped score, capped at 100. No autonomous decision.",
    }

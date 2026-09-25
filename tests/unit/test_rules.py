from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

import pytest

from rules_engine import evaluate, score_risk
from rules_engine.engine import normalize
from scripts.seed import demo_documents, demo_terms


def result(terms, docs, rule):
    return next(r for r in evaluate(terms, docs) if r["rule_id"] == rule)


def test_perfect_case():
    terms = demo_terms()
    assert all(r["status"] in {"PASS", "NOT_APPLICABLE"} for r in evaluate(terms, demo_documents(terms)))


@pytest.mark.parametrize(
    "amount,status", [("100000", "PASS"), ("125000", "PASS"), ("131250", "PASS"), ("131250.01", "FAIL")]
)
def test_tolerance_boundary(amount, status):
    terms = demo_terms()
    docs = demo_documents(terms)
    docs[0]["fields"]["amount"] = amount
    assert result(terms, docs, "AMOUNT_TOLERANCE")["status"] == status


@pytest.mark.parametrize("offset,status", [(0, "PASS"), (1, "FAIL"), (-1, "PASS")])
def test_shipment_boundary(offset, status):
    terms = demo_terms()
    docs = demo_documents(terms)
    docs[1]["fields"]["shipment_date"] = (
        date.fromisoformat(terms["latest_shipment"]) + timedelta(days=offset)
    ).isoformat()
    assert result(terms, docs, "SHIPMENT_DATE")["status"] == status


@pytest.mark.parametrize("offset,status", [(0, "PASS"), (-1, "FAIL"), (1, "PASS")])
def test_expiry_boundary(offset, status):
    terms = demo_terms()
    terms["expiry_date"] = (date.today() + timedelta(days=offset)).isoformat()
    assert result(terms, demo_documents(terms), "LC_EXPIRY")["status"] == status


@pytest.mark.parametrize(
    "scenario,rule",
    [
        ("amount", "AMOUNT_TOLERANCE"),
        ("late", "SHIPMENT_DATE"),
        ("missing", "REQUIRED_DOCUMENTS"),
        ("quantity", "QUANTITY_MATCH"),
    ],
)
def test_scenarios(scenario, rule):
    terms = demo_terms()
    assert result(terms, demo_documents(terms, scenario), rule)["status"] == "FAIL"


def test_normalization_preserves_material_difference():
    assert normalize("ABC Trading Ltd.") == normalize("ABC TRADING LIMITED")
    assert normalize("ABC Trading Limited") != normalize("ABCD Trading Limited")


def test_multiple_discrepancies_and_risk():
    terms = demo_terms()
    results = evaluate(terms, demo_documents(terms, "multiple"))
    assert sum(r["status"] == "FAIL" for r in results) == 4
    risk = score_risk(terms, results)
    assert risk["score"] == 53
    assert risk["score"] == sum(f["points"] for f in risk["factors"])


def test_disabled_rules_and_immutable_inputs():
    terms = demo_terms()
    docs = demo_documents(terms, "amount")
    original = deepcopy(docs)
    rules = {"AMOUNT_TOLERANCE": {"severity": "LOW", "enabled": False, "version": 2}}
    match = next(r for r in evaluate(terms, docs, rules) if r["rule_id"] == "AMOUNT_TOLERANCE")
    assert match["status"] == "NOT_APPLICABLE"
    assert match["rule_version"] == 2
    assert docs == original


def test_all_rules_have_results_and_evidence():
    from rules_engine import CATALOG

    terms = demo_terms()
    results = evaluate(terms, demo_documents(terms))
    assert len(results) == len(CATALOG)
    assert all(r["explanation"] and r["recommendation"] for r in results)


@pytest.mark.parametrize(
    "rule,doc,field,value",
    [
        ("CURRENCY_MATCH", 0, "currency", "EUR"),
        ("INVOICE_ARITHMETIC", 0, "unit_price", "1"),
        ("LINE_TOTALS", 0, "line_totals", ["1"]),
        ("QUANTITY_UNIT", 2, "quantity_unit", "KG"),
        ("PARTY_MATCH", 0, "beneficiary", "Different Company"),
        ("CONSIGNEE_MATCH", 1, "consignee", "Other Party"),
        ("PORT_MATCH", 1, "loading_port", "Other Port"),
        ("SHIPMENT_POLICY", 1, "transshipment", True),
        ("TRANSPORT_REFERENCE", 1, "vessel", ""),
        ("INCOTERM_MATCH", 0, "incoterm", "CIF"),
        ("ORIGIN_COUNTRY", 3, "country", "Other Country"),
        ("DOCUMENT_DATES", 0, "issue_date", "2000-01-01"),
    ],
)
def test_every_rule_failure(rule, doc, field, value):
    terms = demo_terms()
    docs = demo_documents(terms)
    docs[doc]["fields"][field] = value
    assert result(terms, docs, rule)["status"] == "FAIL"


def test_insurance_and_presentation():
    terms = demo_terms()
    terms["incoterm"] = "CIF"
    docs = demo_documents(terms)
    assert result(terms, docs, "INSURANCE_COVER")["status"] == "FAIL"
    docs.append(
        {
            "type": "INSURANCE_CERTIFICATE",
            "fields": {
                "amount": str(Decimal(terms["amount"]) * Decimal("1.1")),
                "currency": terms["currency"],
                "issue_date": terms["issue_date"],
            },
        }
    )
    assert result(terms, docs, "INSURANCE_COVER")["status"] == "PASS"
    terms["presentation_date"] = "2100-01-01"
    assert result(terms, docs, "PRESENTATION_PERIOD")["status"] == "FAIL"
    assert result(terms, docs, "PRESENTATION_EXPIRY")["status"] == "FAIL"

import json

from sqlalchemy import select

from backend.app.audit import verify
from backend.app.models import AuditEvent, LC, User
from backend.app.services import CHECKLIST
from scripts.seed import demo_documents, demo_terms


def make_case(client, headers, scenario="perfect"):
    terms = demo_terms()
    response = client.post(
        "/api/v1/lcs", headers=headers, json={"title": "Synthetic cotton import", "terms": terms}
    )
    assert response.status_code == 201, response.text
    lc = response.json()
    for doc in demo_documents(terms, scenario):
        response = client.post(
            f"/api/v1/lcs/{lc['id']}/documents",
            headers=headers,
            data={"type": doc["type"], "version": lc["version"]},
            files={"file": (doc["type"] + ".json", json.dumps(doc["fields"]).encode(), "application/json")},
        )
        assert response.status_code == 201, response.text
        lc = client.get(f"/api/v1/lcs/{lc['id']}", headers=headers).json()
    return lc


def action(client, headers, lc, action, **extra):
    return client.post(
        f"/api/v1/lcs/{lc['id']}/workflow",
        headers=headers,
        json={
            "action": action,
            "version": lc["version"],
            "reason": "Synthetic review decision with evidence",
            **extra,
        },
    )


def test_full_workflow_persistence_and_audit(system, login):
    client, factory, _ = system
    analyst = login("analyst")
    lc = make_case(client, analyst)
    assert action(client, analyst, lc, "APPROVE").status_code == 409
    lc = action(client, analyst, lc, "SUBMIT").json()
    path = f"/api/v1/lcs/{lc['id']}"
    run = client.post(path + "/validation", headers=analyst)
    assert run.status_code == 200, run.text
    assert client.post(path + "/validation", headers=analyst).json()["id"] == run.json()["id"]
    reviewer = login("reviewer")
    for step in ["START_REVIEW", "COMPLETE_REVIEW", "REQUEST_APPROVAL"]:
        lc = client.get(path, headers=reviewer).json()
        response = action(client, reviewer, lc, step, checklist=CHECKLIST)
        assert response.status_code == 200, response.text
    lc = response.json()
    assert action(client, reviewer, lc, "APPROVE").status_code == 403
    checker = login("checker")
    response = action(client, checker, lc, "APPROVE")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"
    assert action(client, checker, lc, "APPROVE").status_code == 409
    report = client.get(f"/api/v1/reports/lcs/{lc['id']}?format=pdf", headers=checker)
    assert report.content.startswith(b"%PDF")
    with factory() as db:
        assert db.get(LC, lc["id"]).status == "APPROVED"
        assert verify(db)["status"] == "PASS"


def test_discrepancies_and_simulator(system, login):
    client, _, _ = system
    headers = login("analyst")
    lc = make_case(client, headers, "multiple")
    lc = action(client, headers, lc, "SUBMIT").json()
    path = f"/api/v1/lcs/{lc['id']}"
    response = client.post(path + "/validation", headers=headers)
    assert response.status_code == 200
    assert response.json()["risk"]["score"] == 53
    original = client.get(path, headers=headers).json()
    simulation = client.post(path + "/simulate", headers=headers, json={"invoice_amount": "100000"})
    assert simulation.status_code == 200
    assert simulation.json()["persisted"] is False
    assert client.get(path, headers=headers).json()["version"] == original["version"]
    assert len(original["discrepancies"]) == 4


def test_stale_update_and_document_versioning(system, login):
    client, _, _ = system
    headers = login("analyst")
    lc = make_case(client, headers)
    doc = demo_documents(demo_terms())[0]
    old = json.dumps(doc["fields"]).encode()
    path = f"/api/v1/lcs/{lc['id']}"
    assert (
        client.post(
            path + "/documents",
            headers=headers,
            data={"type": doc["type"], "version": lc["version"]},
            files={"file": ("invoice.json", old)},
        ).status_code
        == 409
    )
    doc["fields"]["number"] = "REVISION-2"
    response = client.post(
        path + "/documents",
        headers=headers,
        data={"type": doc["type"], "version": lc["version"], "reason": "Corrected invoice reference"},
        files={"file": ("invoice.json", json.dumps(doc["fields"]).encode())},
    )
    assert response.status_code == 201, response.text
    assert response.json()["version"] == 2
    assert action(client, headers, lc, "SUBMIT").status_code == 409
    current = client.get(path, headers=headers).json()
    assert len(current["documents"]) == 5


def test_hash_chain_detects_tampering(system, login):
    client, factory, _ = system
    login("analyst")
    auditor = login("auditor")
    assert client.post("/api/v1/audit/verify", headers=auditor).json()["status"] == "PASS"
    # Deliberate tampering is isolated to the disposable test database.
    with factory() as db:
        event = db.scalar(select(AuditEvent).order_by(AuditEvent.id))
        event.action = "TAMPERED"
        db.commit()
    assert client.post("/api/v1/audit/verify", headers=auditor).json()["status"] == "FAIL"


def test_four_eyes_survives_role_change(system, login):
    client, factory, _ = system
    analyst = login("analyst")
    lc = make_case(client, analyst)
    lc = action(client, analyst, lc, "SUBMIT").json()
    client.post(f"/api/v1/lcs/{lc['id']}/validation", headers=analyst)
    reviewer = login("reviewer")
    for step in ["START_REVIEW", "COMPLETE_REVIEW", "REQUEST_APPROVAL"]:
        lc = client.get(f"/api/v1/lcs/{lc['id']}", headers=reviewer).json()
        response = action(client, reviewer, lc, step, checklist=CHECKLIST)
        assert response.status_code == 200
    with factory() as db:
        user = db.scalar(select(User).where(User.email == "analyst@lcverify.demo"))
        user.role = "SENIOR_CHECKER"
        db.commit()
    lc = response.json()
    result = action(client, analyst, lc, "APPROVE")
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "MAKER_CHECKER"

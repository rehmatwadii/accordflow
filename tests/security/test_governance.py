from backend.app.models import Incident
from backend.app.services import CHECKLIST
from tests.integration.test_workflow import action, make_case


def test_waiver_authorization_and_current_policy_approval(system, login):
    client, _, _ = system
    analyst = login("analyst")
    lc = make_case(client, analyst, "amount")
    lc = action(client, analyst, lc, "SUBMIT").json()
    path = "/api/v1/lcs/" + lc["id"]
    client.post(path + "/validation", headers=analyst)
    reviewer = login("reviewer")
    lc = client.get(path, headers=reviewer).json()
    lc = action(client, reviewer, lc, "START_REVIEW").json()
    lc = client.get(path, headers=reviewer).json()
    finding = lc["discrepancies"][0]
    payload = {
        "status": "WAIVED",
        "reason": "Synthetic documented exception with supporting evidence",
        "version": lc["version"],
    }
    assert (
        client.patch("/api/v1/discrepancies/" + finding["id"], headers=reviewer, json=payload).status_code
        == 403
    )
    assert action(client, reviewer, lc, "COMPLETE_REVIEW", checklist=CHECKLIST).status_code == 409
    manager = login("manager")
    waived = client.patch("/api/v1/discrepancies/" + finding["id"], headers=manager, json=payload)
    assert waived.status_code == 200, waived.text
    assert waived.json()["result"]["status"] == "FAIL"
    lc = client.get(path, headers=reviewer).json()
    assert action(client, reviewer, lc, "COMPLETE_REVIEW", checklist=[]).status_code == 422
    lc = action(client, reviewer, lc, "COMPLETE_REVIEW", checklist=CHECKLIST).json()
    lc = action(client, reviewer, lc, "REQUEST_APPROVAL").json()
    admin = login("admin")
    response = client.patch(
        "/api/v1/rules/AMOUNT_TOLERANCE",
        headers=admin,
        json={
            "severity": "CRITICAL",
            "enabled": True,
            "version": 1,
            "reason": "Synthetic stricter amount policy",
        },
    )
    assert response.status_code == 200, response.text
    checker = login("checker")
    result = action(client, checker, lc, "APPROVE")
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "STALE_VALIDATION"


def test_critical_missing_document_cannot_be_waived(system, login):
    client, _, _ = system
    analyst = login("analyst")
    lc = make_case(client, analyst, "missing")
    lc = action(client, analyst, lc, "SUBMIT").json()
    path = "/api/v1/lcs/" + lc["id"]
    client.post(path + "/validation", headers=analyst)
    manager = login("manager")
    lc = client.get(path, headers=manager).json()
    lc = action(client, manager, lc, "START_REVIEW").json()
    lc = client.get(path, headers=manager).json()
    finding = next(d for d in lc["discrepancies"] if d["rule_id"] == "REQUIRED_DOCUMENTS")
    response = client.patch(
        "/api/v1/discrepancies/" + finding["id"],
        headers=manager,
        json={
            "status": "WAIVED",
            "version": lc["version"],
            "reason": "Intentional negative authorization test",
        },
    )
    assert response.status_code == 409


def test_role_changes_revoke_sessions_and_configuration_is_versioned(system, login):
    client, factory, _ = system
    analyst = login("analyst")
    admin = login("admin")
    users = client.get("/api/v1/users", headers=admin).json()
    user = next(u for u in users if u["role"] == "TRADE_ANALYST")
    response = client.patch(
        "/api/v1/users/" + user["id"],
        headers=admin,
        json={"role": "INTERNAL_AUDITOR", "active": True, "reason": "Synthetic access review adjustment"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me", headers=analyst).status_code == 401
    settings = client.get("/api/v1/settings", headers=admin).json()
    version = next(s["version"] for s in settings if s["key"] == "sla_hours")
    assert (
        client.put(
            "/api/v1/settings/sla",
            headers=admin,
            json={
                "standard_hours": 30,
                "high_hours": 10,
                "critical_hours": 3,
                "version": version,
                "reason": "Synthetic updated SLA definition",
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/settings/sla",
            headers=admin,
            json={
                "standard_hours": 30,
                "high_hours": 10,
                "critical_hours": 3,
                "version": version,
                "reason": "Repeat stale policy update",
            },
        ).status_code
        == 409
    )


def test_signal_investigation_and_worker_authorization(system, login):
    client, factory, _ = system
    auditor = login("auditor")
    assert client.post("/api/v1/jobs/run", headers=auditor).status_code == 403
    admin = login("admin")
    assert client.post("/api/v1/jobs/run", headers=admin).status_code == 200
    with factory() as db:
        incident = Incident(
            source_key="SYNTHETIC-TEST", title="Synthetic investigation", details={"synthetic": True}
        )
        db.add(incident)
        db.commit()
        incident_id = incident.id
    assert client.get("/api/v1/incidents", headers=admin).json()[0]["id"] == incident_id
    assert (
        client.patch(
            "/api/v1/incidents/" + incident_id,
            headers=admin,
            json={"status": "RESOLVED", "reason": "Synthetic finding reviewed and documented"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/jobs", headers=admin).status_code == 200


def test_chunked_oversized_request_rejected_before_parser(system, login):
    client, _, _ = system
    headers = login("analyst")

    def chunks():
        for _ in range(7):
            yield b"x" * 1024 * 1024

    response = client.post(
        "/api/v1/lcs", headers={**headers, "Content-Type": "application/json"}, content=chunks()
    )
    assert response.status_code == 413

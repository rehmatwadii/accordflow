from datetime import timedelta

import pytest
from sqlalchemy import select

from backend.app.models import LC, Session, User, now
from scripts.seed import demo_terms
from tests.integration.test_workflow import make_case


def test_anonymous_and_admin_separation(system, login):
    client, _, _ = system
    assert client.get("/api/v1/lcs").status_code == 401
    admin = login("admin")
    assert client.get("/api/v1/lcs", headers=admin).status_code == 403
    auditor = login("auditor")
    assert (
        client.post(
            "/api/v1/lcs", headers=auditor, json={"title": "Synthetic LC", "terms": demo_terms()}
        ).status_code
        == 403
    )
    assert client.delete("/api/v1/audit/1", headers=auditor).status_code in {404, 405}
    assert (
        client.patch(
            "/api/v1/rules/AMOUNT_TOLERANCE",
            headers=auditor,
            json={"severity": "LOW", "enabled": False, "version": 1, "reason": "Unauthorized change"},
        ).status_code
        == 403
    )


def test_idor_case_documents_export_and_simulation(system, login):
    client, factory, _ = system
    analyst = login("analyst")
    lc = make_case(client, analyst)
    doc = lc["documents"][0]
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "checker@lcverify.demo"))
        db.get(LC, lc["id"]).created_by = owner.id
        db.commit()
    assert client.get(f"/api/v1/lcs/{lc['id']}", headers=analyst).status_code == 404
    assert client.get(f"/api/v1/documents/{doc['id']}/download", headers=analyst).status_code == 404
    assert client.get(f"/api/v1/reports/lcs/{lc['id']}", headers=analyst).status_code == 404
    assert (
        client.post(
            f"/api/v1/lcs/{lc['id']}/simulate", headers=analyst, json={"invoice_amount": 100}
        ).status_code
        == 404
    )
    assert client.get("/api/v1/lcs", headers=analyst).json()["total"] == 0


@pytest.mark.parametrize(
    "filename,content",
    [
        ("evil.exe", b"MZbad"),
        ("../invoice.json", b"{}"),
        ("invoice.pdf", b"not a PDF"),
        ("bad.json", b"not json"),
        ("active.pdf", b"%PDF-1.4 /JavaScript test %%EOF"),
    ],
)
def test_hostile_uploads(system, login, filename, content):
    client, _, _ = system
    headers = login("analyst")
    lc = client.post(
        "/api/v1/lcs", headers=headers, json={"title": "Synthetic LC", "terms": demo_terms()}
    ).json()
    response = client.post(
        f"/api/v1/lcs/{lc['id']}/documents",
        headers=headers,
        data={"type": "COMMERCIAL_INVOICE", "version": lc["version"]},
        files={"file": (filename, content)},
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount", "-1"),
        ("amount", "99999999999999999999999"),
        ("amount", "NaN"),
        ("currency", "XXX"),
        ("issue_date", "2026-02-30"),
        ("quantity", 0),
        ("applicant", " "),
    ],
)
def test_invalid_business_inputs(system, login, field, value):
    client, _, _ = system
    headers = login("analyst")
    terms = demo_terms()
    terms[field] = value
    response = client.post("/api/v1/lcs", headers=headers, json={"title": "Synthetic LC", "terms": terms})
    assert response.status_code == 422
    assert "correlation_id" in response.json()["error"]


def test_mass_assignment_malformed_json_and_injection(system, login):
    client, _, _ = system
    headers = login("analyst")
    body = {"title": "Synthetic LC", "terms": demo_terms(), "status": "APPROVED", "created_by": "attacker"}
    assert client.post("/api/v1/lcs", headers=headers, json=body).status_code == 422
    assert client.post("/api/v1/lcs", headers=headers, content="{bad json").status_code == 422
    response = client.get("/api/v1/lcs", headers=headers, params={"q": "' OR 1=1; DROP TABLE users;--"})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_refresh_rotation_replay_logout(system, login):
    client, _, _ = system
    headers = login("analyst")
    original = client.cookies.get("lcv_refresh")
    assert client.post("/api/v1/auth/refresh").status_code == 403
    trusted = {"origin": "http://localhost:5173", "x-lcv-client": "workbench"}
    rotated = client.post("/api/v1/auth/refresh", headers=trusted)
    assert rotated.status_code == 200, rotated.text
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    new_headers = {"Authorization": "Bearer " + rotated.json()["access_token"]}
    client.cookies.clear()
    client.cookies.set("lcv_refresh", original, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh", headers=trusted).status_code == 401
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 401
    headers = login("analyst")
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_lockout_and_rate_limit(system):
    client, _, password = system
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": "analyst@lcverify.demo", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "analyst@lcverify.demo", "password": password}
        ).status_code
        == 401
    )
    for _ in range(10):
        response = client.post(
            "/api/v1/auth/login", json={"email": "nobody@lcverify.demo", "password": "wrong"}
        )
    assert response.status_code == 429


def test_expired_token_and_security_headers(system, login):
    client, factory, _ = system
    headers = login("analyst")
    with factory() as db:
        session = db.scalar(select(Session))
        session.access_expires = now() - timedelta(seconds=1)
        db.commit()
    response = client.get("/api/v1/lcs", headers=headers)
    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-correlation-id"].startswith("LCV-REQ-")

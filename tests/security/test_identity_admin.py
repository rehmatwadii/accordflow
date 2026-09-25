import secrets


def test_provisioning_reset_and_session_revocation(system, login):
    client, _, _ = system
    auditor = login("auditor")
    password = "Synthetic-" + secrets.token_urlsafe(16) + "7aA"
    body = {
        "name": "Synthetic New Analyst",
        "email": "new.analyst@lcverify.demo",
        "role": "TRADE_ANALYST",
        "password": password,
        "reason": "Synthetic role provisioning regression",
    }
    assert client.post("/api/v1/users", headers=auditor, json=body).status_code == 403
    admin = login("admin")
    created = client.post("/api/v1/users", headers=admin, json=body)
    assert created.status_code == 201, created.text
    assert "password_hash" not in created.json()
    assert client.post("/api/v1/users", headers=admin, json=body).status_code == 409
    signed_in = client.post("/api/v1/auth/login", json={"email": body["email"], "password": password})
    headers = {"Authorization": "Bearer " + signed_in.json()["access_token"]}
    sessions = client.get("/api/v1/auth/sessions", headers=headers).json()
    assert len(sessions) == 1
    replacement = "Replacement-" + secrets.token_urlsafe(16) + "8bB"
    reset = client.put(
        "/api/v1/users/" + created.json()["id"] + "/password",
        headers=admin,
        json={"password": replacement, "reason": "Synthetic admin-assisted reset regression"},
    )
    assert reset.status_code == 200, reset.text
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        client.post("/api/v1/auth/login", json={"email": body["email"], "password": password}).status_code
        == 401
    )
    assert (
        client.post("/api/v1/auth/login", json={"email": body["email"], "password": replacement}).status_code
        == 200
    )


def test_current_user_cannot_revoke_someone_elses_session(system, login):
    client, _, _ = system
    analyst = login("analyst")
    session = client.get("/api/v1/auth/sessions", headers=analyst).json()[0]
    auditor = login("auditor")
    assert client.delete("/api/v1/auth/sessions/" + session["id"], headers=auditor).status_code == 404
    assert client.delete("/api/v1/auth/sessions/" + session["id"], headers=analyst).status_code == 200
    assert client.get("/api/v1/auth/me", headers=analyst).status_code == 401

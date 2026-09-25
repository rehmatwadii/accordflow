"""Generate runnable positive and negative API examples from today's synthetic fixture."""

import json
from pathlib import Path

from scripts.seed import demo_documents, demo_terms

terms = demo_terms()
Path("postman/fixtures").mkdir(parents=True, exist_ok=True)
for doc in demo_documents(terms):
    Path(f"postman/fixtures/{doc['type']}.json").write_text(
        json.dumps(doc["fields"], indent=2), encoding="utf-8"
    )

items = []


def request(name, method, path, body=None, expected=200, script=None, auth=True, form=None):
    req = {
        "method": method,
        "header": [{"key": "Authorization", "value": "Bearer {{access_token}}"}] if auth else [],
        "url": "{{base_url}}/api/v1" + path,
    }
    if body is not None:
        req["header"].append({"key": "Content-Type", "value": "application/json"})
        req["body"] = {"mode": "raw", "raw": json.dumps(body)}
    if form:
        req["body"] = {"mode": "formdata", "formdata": form}
    checks = [
        f"pm.test('Expected status {expected}', () => pm.response.to.have.status({expected}));",
        "pm.test('Correlation ID present', () => pm.expect(pm.response.headers.get('X-Correlation-ID')).to.match(/^LCV-REQ-/));",
    ]
    if script:
        checks.extend(script)
    items.append(
        {
            "name": name,
            "request": req,
            "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": checks}}],
        }
    )


def login(role):
    request(
        "Login as " + role,
        "POST",
        "/auth/login",
        {"email": role + "@lcverify.demo", "password": "{{demo_password}}"},
        auth=False,
        script=["pm.environment.set('access_token', pm.response.json().access_token);"],
    )


login("analyst")
request("Current user", "GET", "/auth/me")
request("Role catalog", "GET", "/roles")
request(
    "Create synthetic case",
    "POST",
    "/lcs",
    {"title": "Newman synthetic import", "terms": terms},
    201,
    script=[
        "pm.environment.set('lc_id', pm.response.json().id); pm.environment.set('version', pm.response.json().version);"
    ],
)
request(
    "Reject skipped approval",
    "POST",
    "/lcs/{{lc_id}}/workflow",
    {"action": "APPROVE", "version": "{{version}}", "reason": "Deliberate invalid transition regression"},
    409,
)
for doc in demo_documents(terms):
    request(
        "Upload " + doc["type"],
        "POST",
        "/lcs/{{lc_id}}/documents",
        expected=201,
        form=[
            {"key": "type", "type": "text", "value": doc["type"]},
            {"key": "version", "type": "text", "value": "{{version}}"},
            {"key": "file", "type": "file", "src": f"postman/fixtures/{doc['type']}.json"},
        ],
    )
    request(
        "Refresh case version",
        "GET",
        "/lcs/{{lc_id}}",
        script=["pm.environment.set('version', pm.response.json().version);"],
    )
request(
    "Submit case",
    "POST",
    "/lcs/{{lc_id}}/workflow",
    {"action": "SUBMIT", "version": "{{version}}", "reason": "Synthetic Newman case submission"},
)
request(
    "Run deterministic validation",
    "POST",
    "/lcs/{{lc_id}}/validation",
    script=[
        "pm.environment.set('run_id', pm.response.json().id); pm.test('All checks pass or are inapplicable', () => pm.expect(pm.response.json().results.every(r => ['PASS','NOT_APPLICABLE'].includes(r.status))).to.equal(true));"
    ],
)
request(
    "Validation is idempotent",
    "POST",
    "/lcs/{{lc_id}}/validation",
    script=[
        "pm.test('Same run ID', () => pm.expect(pm.response.json().id).to.equal(pm.environment.get('run_id')));"
    ],
)
request("List discrepancies", "GET", "/discrepancies")
request(
    "Add investigation note",
    "POST",
    "/lcs/{{lc_id}}/comments",
    {"body": "Synthetic API test note with documentary evidence reviewed."},
    201,
)
request("Rules catalog", "GET", "/rules")
request("Dashboard metrics", "GET", "/reports/dashboard")
request("Controlled export", "GET", "/reports/export?format=json")
request("Compliance report", "GET", "/reports/lcs/{{lc_id}}")
request("Notifications", "GET", "/notifications")
request("Deny admin users to analyst", "GET", "/users", expected=403)
request("Logout", "POST", "/auth/logout")
request("Reject revoked access token", "GET", "/auth/me", expected=401)
login("auditor")
request("Audit explorer", "GET", "/audit")
request(
    "Audit chain verification",
    "POST",
    "/audit/verify",
    script=["pm.test('Integrity PASS', () => pm.expect(pm.response.json().status).to.equal('PASS'));"],
)
request("Logout auditor", "POST", "/auth/logout")
collection = {
    "info": {
        "name": "AccordFlow",
        "description": "Synthetic local-only API assurance. Run from repository root. Generate fixtures immediately before execution.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "item": items,
}
Path("postman/AccordFlow.postman_collection.json").write_text(
    json.dumps(collection, indent=2), encoding="utf-8"
)
Path("postman/AccordFlow.postman_environment.json").write_text(
    json.dumps(
        {
            "name": "AccordFlow local synthetic demo",
            "values": [
                {"key": "base_url", "value": "http://127.0.0.1:8000", "enabled": True},
                {"key": "demo_password", "value": "", "enabled": True, "type": "secret"},
            ],
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(f"Generated {len(items)} Postman requests and synthetic file fixtures")

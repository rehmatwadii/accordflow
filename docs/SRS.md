# Software requirements specification

| ID | Requirement | Current acceptance boundary |
|---|---|---|
| FR-AUTH-001 | Authenticate and revoke sessions | Argon2id, opaque tokens, rotation/replay checks, logout |
| FR-LC-001 | Create and amend LC terms | Validated inputs, persisted versions, optimistic locks |
| FR-DOC-001 | Store synthetic document evidence | 5 MB cap, signatures, hashes, protected version history |
| FR-VAL-001 | Run deterministic checks | 20 rules, exact decimals, evidence and frozen input |
| FR-RISK-001 | Explain risk score | Weighted factors, capped total, visible system score |
| FR-WF-001 | Enforce lifecycle | Allowed transitions only; invalid moves return controlled 409 |
| FR-APP-001 | Require independent approval | Checklist, current validation, no unresolved mandatory blockers |
| FR-EXC-001 | Record human discrepancy decisions | Authorized noncritical waivers with mandatory justification |
| FR-AUD-001 | Append and verify audit trail | Event hash chain and singleton head; no public mutation API |
| FR-REP-001 | Report and export | Scoped dashboard/CSV/JSON/PDF with export audit |
| FR-SLA-001 | Detect service-level concerns | Deadline policy, computed state, idempotent worker notices |
| FR-NOT-001 | Queue notifications | In-app plus transactional mock email outbox |
| FR-SIM-001 | Simulate invoice changes | Pure evaluation; no LC/document/validation writes |
| FR-ADM-001 | Administer configuration | Versioned rule/SLA changes and user role/deactivation |
| FR-INC-001 | Investigate operational signals | Worker identifies failed-login/replay signals; admin decisions |
| NFR-SEC-001 | Enforce server-side authorization | Permission checks plus ownership/assignment scope |
| NFR-SEC-002 | Limit hostile inputs | Strict Pydantic schemas, parameterized ORM, payload/file limits |
| NFR-OBS-001 | Correlate errors and events | Generated request IDs, consistent safe errors, structured logs |
| NFR-QA-001 | Automate core behavior | Pytest, Newman, Playwright, dependency scans |
| NFR-UX-001 | Support accessible operations | Semantic controls, labels/descriptions, focus rings, themes |

Authentication lifetimes: access 15 minutes; session refresh 8 hours maximum, with rotation. Five failed account logins begin progressive temporary lockout. Rate buckets are per-process, per source address and endpoint category; deployment-wide rate enforcement remains a production gap.

API prefix: `/api/v1`. List endpoints have bounded pages; export caps at 1,000 accessible cases. Document JSON follows `DocumentFields` in OpenAPI. Unexpected request fields are rejected to prevent mass assignment. Errors contain code, message, safe field details and correlation ID.

Configuration profiles are selected using `APP_ENV` (demo/development/test/production). Production requires PostgreSQL and explicit HTTPS origins, prohibits `DEMO_PASSWORD`, and disables synthetic seeding. This guard is necessary but does not constitute production readiness.

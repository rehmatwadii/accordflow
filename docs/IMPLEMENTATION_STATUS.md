# Implementation status against the master prompt

The supplied 149-section prompt is broader than the delivered portfolio release. This document is the scope boundary, not a claim that every item is finished.

| Area | State |
|---|---|
| Foundation, Python/React projects, locked dependencies, migrations | Implemented; local SQLite verified |
| PostgreSQL / Docker deployment | Configuration supplied; local Docker engine unavailable, execution pending |
| Authentication, hashed passwords, rotation/revocation, lockout, device/session records | Implemented |
| Password reset / MFA | Audited administrator-assisted local demo reset implemented; self-service recovery and MFA architecture documented |
| RBAC / assignment and ownership ABAC | Implemented; code-defined role matrix, single organization |
| LC terms, versions, lifecycle and optimistic locking | Implemented |
| Document upload, hashing, duplicate rejection, versions and scoped download | Implemented |
| OCR / malware / AI | Local text-PDF layout extraction plus OCR.space scan/image extraction with editable field review; JSON/manual fallback and demo scanner; no production AV/AI |
| Deterministic rules, required-document profiles, risk and evidence | Twenty rules; simplified profile semantics; no jurisdictional country-risk engine |
| Discrepancies, notes, waivers, assignment, checklist and independent checker | Implemented |
| Case queues, search, filter, sort, pagination and local saved view | Implemented; search is LC/reference/terms, not every entity in the master prompt |
| Audit, hash-chain verification, correlation IDs and version history | Implemented at application level |
| SLA definitions, computed warnings/breaches and worker escalation notices | Implemented; fixed two-hour warning window |
| Notifications/outbox/retries/dead state | Implemented using no-transmission mock provider |
| Validation/report background execution | Synchronous in this release |
| Operational signals and investigation decisions | Implemented for failed-login/replay signals; not a SIEM/fraud detector |
| Dashboard, trends, reports, CSV/JSON/PDF | Implemented; synthetic DB metrics, small-portfolio queries |
| Rule simulation / what-if | Invoice amount simulation implemented; general multi-field simulator pending |
| Admin users / configuration | Synthetic account provisioning, role/active changes, demo reset, rule history and SLA settings implemented |
| API documentation | Live/exported OpenAPI; typed auth/LC/document/validation contracts; some governance/report responses remain generic |
| Pytest / Newman / Playwright / SQL / load probe | Executed locally; details in TEST_RESULTS.md |
| Dependency / secret scanning | Executed; Newman-only exceptions documented |
| CI | Workflow authored; hosted execution pending repository setup |
| Business / QA / security / portfolio documentation | Included |
| Production certification / high availability / legal interpretation | Explicitly not claimed |

Next engineering increments should prioritize PostgreSQL execution, response-contract typing, IAM/recovery, production upload scanning and broader race/outage testing before adding more visible features.

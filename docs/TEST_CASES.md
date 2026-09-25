# Test case catalog

All data is synthetic. API precondition: migrated isolated test database with seven roles. UI precondition: local server, current demo seed and local generated password.

| ID | Priority / type | Steps | Expected |
|---|---|---|---|
| TC-AUTH-001 | P0 / security | Login, rotate refresh, use old access | New access works; old access rejected |
| TC-AUTH-002 | P0 / security | Replay consumed refresh | Session family revoked |
| TC-AUTH-003 | P0 / security | Fail five logins; attempt correct password | Temporary account lockout |
| TC-LC-001 | P1 / integration | Create draft, amend with current version | Terms snapshot and audit preserved |
| TC-LC-002 | P0 / concurrency | Two requests use same case version | One mutation wins; other controlled conflict |
| TC-DOC-001 | P0 / security | Upload executable, path traversal or mismatched PDF | 422; nothing persisted |
| TC-DOC-002 | P1 / integration | Upload same bytes, then corrected same-type file | Duplicate 409; revised file is v2 |
| TC-VAL-001 | P0 / boundary | Invoice exactly at tolerance and 0.01 above | PASS, then FAIL |
| TC-VAL-002 | P0 / boundary | Shipment on deadline and one day later | PASS, then FAIL |
| TC-VAL-003 | P0 / boundary | Expiry is today, yesterday, tomorrow | PASS, FAIL, PASS |
| TC-VAL-004 | P1 / unit | Compare normalized legal suffixes/materially different names | Normalized match distinguished from mismatch |
| TC-VAL-005 | P1 / integration | Validate unchanged input twice | Same validation-run ID |
| TC-WF-001 | P0 / security | Attempt draft→approved | Controlled 409 |
| TC-WF-002 | P0 / integration | Submit, validate, review checklist, request checker | Pending checker only after completed checks |
| TC-SEC-001 | P0 / authorization | Change owner; original analyst reads case/file/report | Controlled 404 for every object boundary |
| TC-SEC-002 | P0 / authorization | Promote maker's role then approve own case | 403 maker-checker block |
| TC-SEC-003 | P0 / input | Unexpected status/actor fields, invalid amounts/dates, SQL payload | Invalid input rejected; search cannot alter DB |
| TC-SEC-004 | P0 / authorization | Admin/auditor attempts business writes | 403; auditor cannot alter audit |
| TC-AUD-001 | P0 / integrity | Modify disposable audit event and verify | FAIL identifies inconsistent chain |
| TC-JOB-001 | P1 / failure | Mock provider throws on three attempts | RETRY/backoff then DEAD, no infinite retries |
| TC-SLA-001 | P1 / integration | Monitor overdue case twice | One idempotent SLA event, in-app escalation |
| TC-E2E-001 | P0 / UI | Create→four uploads→submit→validate→review→checker | Approved persisted case with visible audit |
| TC-E2E-002 | P1 / UI | Toggle theme, search seeded case, compare evidence | Readable views and matching evidence |
| TC-E2E-003 | P0 / UI | Auditor verifies; admin opens workspace | Integrity PASS; no admin operational links |

Rule test parametrization additionally exercises quantity, units, ports, consignee, notify party, currency, arithmetic, line totals, Incoterm, insurance and transport reference. See test source for exact fixtures/assertions.

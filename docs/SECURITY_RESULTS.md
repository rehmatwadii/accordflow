# Security verification results

Initial local verification: 24 September 2026, Windows, Python 3.12, Node 24, SQLite. Results apply to this demonstration build, not a penetration test or certification.

## Application dependencies

- `pip-audit -r requirements.lock.txt`: no known vulnerabilities reported.
- `npm audit` in `frontend/`: zero vulnerabilities reported, including its development dependencies at the time scanned.
- Locks preserve the resolved dependency graph. Rescan before distributing/deploying; advisory databases change.
- `scripts/secret_scan.py`: no supported private-key/token patterns in project source. This intentionally limited heuristic does not prove the absence of every secret type.
- `.env`, `.demo-credentials.json`, virtual environments, node_modules, runtime data and test artifacts are ignored. No actual password, token or database credential is committed.

## Isolated Postman/Newman tooling

Newman 6.2.2 is installed only under `postman/`, not the React or backend runtime. Its legacy dependency graph initially reported 19 vulnerable package nodes including a critical Handlebars dependency. Compatible patched overrides were applied to Handlebars, Lodash, Flatted, node-forge, qs, Underscore, jose and UUID. The complete 30-request/63-assertion collection passed after those overrides.

Two upstream root advisories remain; npm reports six affected package nodes through dependency propagation (five high, one moderate):

| Root package | Advisory | Local exception boundary |
|---|---|---|
| `@faker-js/faker` legacy API | `GHSA-qxc2-j82w-r537` | No Faker templates/macros or untrusted collections are executed |
| `csv-parse` legacy callable API | `GHSA-8cw4-87c7-c6xx` | Runner uses generated JSON fixtures; CSV input is not used |

No arbitrary major-version override was imposed on those incompatible APIs. The runner accepts only this repository's trusted local synthetic collection; no production credentials or remote systems belong in it. `scripts/audit_postman.py` preserves the full scan and fails on new root advisory IDs or an expired review. The exception expires **24 October 2026**. It is a documented test-tool limitation, not a clean dependency report or a blanket risk acceptance for deployment.

## Regression controls exercised

Unauthorized/IDOR access, administrator/business-role separation, immutable audit API boundary, maker/reviewer/checker separation after role changes, stale policy approval, non-waivable critical findings, refresh replay, access expiry, logout, cross-user session revocation, account lockout, endpoint throttling, oversized streamed bodies, executable/path/signature uploads, unexpected fields, malformed JSON, SQL-like search input and invalid dates/decimals.

Tests also exercise audit tamper detection in disposable databases, exactly one successful concurrent submission, and bounded notification retries. Tests do not establish universal resistance to all attacks or production database concurrency behavior.

## Unverified security work

Independent penetration test, real antivirus/content disarm, enterprise IAM/MFA/self-service recovery, distributed rate enforcement, SIEM/WORM storage, encryption/key-management deployment, PostgreSQL privilege/HA review, comprehensive XSS/CSRF browser attack automation and regulatory policy validation. See THREAT_MODEL.md and PRODUCTION_GAP_ANALYSIS.md.

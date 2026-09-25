# Executed verification

Verified locally on **24 September 2026**, Windows, Python 3.12.6, Node 24.20.0, SQLite, Chromium headless. All values below come from actual execution.

| Check | Result |
|---|---|
| Pytest unit/integration/security | **65 passed** |
| Python statement coverage | **88.33%** (1,309 / 1,482 statements) |
| Rule engine coverage | **97%** |
| Audit module coverage | **100%** |
| Core service coverage | **94%** |
| Playwright browser journeys | **4 passed**, 22.7 seconds |
| Newman collection | **30 requests / 63 assertions passed** |
| TypeScript strict build, unused-symbol checks, Vite production bundle | **Passed** |
| Ruff check and formatting check | **Passed** |
| Fresh migrations: upgrade, schema diff check, downgrade, re-upgrade | **Passed** on a disposable SQLite database |
| Database foreign-key/integrity probes and complete audit chain | **Passed**; chain length varies with real demo actions |
| SQLite online backup and restore into a new verified database | **Passed** |
| Documented Windows stop/start scripts | **Passed**; dependency install, migrations, seed preservation, frontend build and readiness check |
| Docker Compose configuration validation | **Passed** (`docker compose config --quiet`) |
| Docker / PostgreSQL runtime | **Not executed locally**: Docker engine unavailable |
| Hosted GitHub Actions | **Not executed**: workflow supplied, no repository push performed |
| Python dependency scan | **No known vulnerabilities reported** |
| Frontend dependency scan | **0 vulnerabilities reported** |
| Newman-only tool scan | **2 upstream root advisories**, documented dated exception; no critical finding after compatible overrides |
| Heuristic source secret scan | **No supported patterns found** |

The current Python dependency stack emits one Starlette warning that its httpx-backed test client is deprecated. Tests still pass; future dependency maintenance should migrate when the replacement stabilizes. This is not suppressed or counted as a functional failure.

## Browser journeys

1. Analyst signs in, sees database-derived portfolio, toggles dark/light theme, searches an existing case and compares validation evidence, then signs out.
2. Analyst creates a new synthetic credit, uploads four documents, submits and validates; a reviewer completes the checklist; an independent checker approves; the case audit is visible.
3. Auditor verifies chain integrity; system administrator cannot access operational navigation and can inspect rules.
4. Administrator provisions a synthetic account and runs the worker; the new user signs in and inspects their sessions.

Screenshots are available under `docs/screenshots/`. Real interactions create additional synthetic test cases/users in the local demo; counters are recalculated from those records, not held at a fixed seed total.

## Local read-load probe

50 authenticated requests, concurrency 5, alternating paginated case lists and dashboard:

- Errors: 0
- Mean: 199.38 ms
- p95: 355.40 ms
- Maximum: 506.63 ms

This small probe describes one development machine and a small synthetic portfolio. It is not a scalability or service-level guarantee.

## Material limits

No independent penetration test, real PostgreSQL execution on this host, actual cloud deployment, production OCR/antivirus, real email delivery, regulatory validation, full accessibility certification or disaster-recovery exercise was performed. Migration rollback checks used disposable empty schemas; downgrading a real database is destructive and requires a separately reviewed recovery plan.

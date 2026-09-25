# Production gap analysis

LC-Verify is a sophisticated **synthetic portfolio demonstration**, not a certified, regulator-approved or bank-ready production system.

## Required before real banking use

- Formal bank-specific policy validation, legal and regulatory review, official ICC/UCP interpretation licensing/validation, and sanctions/financial-crime systems appropriate to jurisdiction.
- Enterprise IAM/OIDC/SAML, enforced MFA, secure enrollment/recovery, approved password reset delivery, step-up authentication and recurring access recertification.
- HSM/KMS-managed keys, defined encryption/data-residency controls, TLS termination, segregated networks and least-privilege production database accounts.
- Full antivirus/content-disarm pipeline, safe document rendering sandbox, approved OCR, confidence/quality review, secure object storage, document retention/hold policy.
- Independent penetration test, secure design review, privacy impact assessment, supply-chain controls, signed images, SBOM, vendor risk management and resolution of development-tool advisories.
- Immutable/WORM audit storage and external chain anchoring, SIEM/SOC integration, monitored incident procedures and evidence preservation.
- PostgreSQL migration/concurrency/restore verification on the actual target version and deployment topology; high availability, failover, backups, disaster recovery exercises and agreed RPO/RTO.
- Distributed rate limits, durable work scheduling, delivery idempotency, lock/lease management, reprocessing controls, capacity planning and performance monitoring.
- Formal software release/change management, segregation of environments, validated model/rule governance and independently reviewed overrides.
- Comprehensive browser/device/accessibility assessment and contract/schema coverage for all administrative/reporting responses.

## Current simplifications

One synthetic organization; code-defined roles instead of a fully relational permission designer. LCs act as the case aggregate. Terms/evidence snapshots and validation results use JSON. Document bytes live in the relational database. Reviewer scope is assignment-based; managers/checkers/auditors have broader role scopes.

Validation and PDF generation are synchronous. Notifications alone have a transactional outbox and bounded worker. SLA warning threshold is fixed at two hours; configurable durations affect new cases only. Severity weights and high-value thresholds are demo policy, with no FX normalization. Country-of-origin matching is a consistency check, not country/sanctions risk screening.

The scanner is not real malware protection. PDF/images require manual fields; structured JSON is the only automatic extraction. No AI provider is enabled. Synthetic account provisioning, role/deactivation and administrator-assisted demo password reset work. Production self-service recovery and MFA are architecture notes, not working integrations.

Metrics and rate limits are per process, so restarting resets operational counters. Dashboard aggregation is bounded by the demonstration portfolio rather than designed for millions of records. Chain hashes provide application tamper evidence only. SQLite lock behavior is not representative of PostgreSQL under real load.

Docker and hosted CI configurations are supplied; the initial Windows environment had no running Docker engine. Do not describe those paths as locally proven until they have been executed. See TEST_RESULTS.md for exactly what was verified.

## Recovery and retention

The online SQLite backup script uses the database backup API. Restore writes a new database path after integrity checks; operators stop the service before switching it. PostgreSQL production backups require `pg_dump`/WAL/archive mechanisms, encrypted storage, access controls and measured restores. Example demo commands:

```powershell
.venv/Scripts/python -m scripts.backup_db data/backups/demo-2026-09-24.db
.venv/Scripts/python -m scripts.restore_db data/backups/demo-2026-09-24.db data/restored-demo.db
```

Audit retention is indefinite in this demo; automatic deletion is not implemented. Legal hold, archival, retention and deletion policy require organizational approval. RPO/RTO are deliberately not promised without measured infrastructure.

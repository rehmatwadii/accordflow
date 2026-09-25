# Requirements traceability matrix

Status means the functionality has an automated check; consult TEST_RESULTS.md for the latest executed platform and limitations.

| Requirement | API / service | Entity | UI | Test | Status |
|---|---|---|---|---|---|
| FR-AUTH-001 | `/auth/login`, `/refresh`, `/logout` | users/sessions/used_refresh_tokens | Login | `test_refresh_rotation_replay_logout` | Automated |
| FR-LC-001 | `/lcs`, `create_lc` | lcs/lc_versions | Case form / terms | `test_stale_update_and_document_versioning` | Automated |
| FR-DOC-001 | `/lcs/{id}/documents` | documents | Document tab | `test_hostile_uploads`, E2E full workflow | Automated |
| FR-VAL-001 | `/lcs/{id}/validation` | validation_runs | Validation / comparison | `test_rules.py`, full API workflow | Automated |
| FR-RISK-001 | `score_risk` | validation_runs/lcs | Risk tab / dashboard | `test_multiple_discrepancies_and_risk` | Automated |
| FR-WF-001 | `/lcs/{id}/workflow` | lcs/approvals | Next step | `test_full_workflow_persistence_and_audit` | Automated |
| FR-APP-001 | `ensure_approval_ready` | approvals | Checker dialog | `test_four_eyes_survives_role_change`, E2E | Automated |
| FR-EXC-001 | `/discrepancies/{id}` | discrepancies | Findings / decisions | API regression suite | Automated |
| FR-AUD-001 | `/audit`, `/audit/verify` | audit_events/audit_head | Audit explorer | `test_hash_chain_detects_tampering` | Automated |
| FR-REP-001 | `/reports/*` | Read models | Reports / case PDF | Newman / API full workflow | Automated |
| FR-SLA-001 | `jobs.monitor` | lcs/outbox_events | SLA badges / reports | `test_monitor_is_idempotent_and_provider_retries_are_bounded` | Automated |
| FR-NOT-001 | `providers`, `jobs.deliver` | notifications/outbox_events | Notifications / admin jobs | Bounded retry test | Automated |
| FR-SIM-001 | `/lcs/{id}/simulate` | Read-only snapshots | Risk simulator | `test_discrepancies_and_simulator` | Automated |
| FR-ADM-001 | `/users`, `/rules`, `/settings` | users/rules/settings/audit | Admin / catalog | Role separation tests / browser admin | Automated |
| FR-INC-001 | `/incidents`, monitor | security_incidents | Admin signals | Job/API tests | Automated |
| NFR-SEC-001 | `require`, `scope`, `get_lc` | users/lcs | Permissions reflected | `test_idor_case_documents_export_and_simulation` | Automated |
| NFR-SEC-002 | schema/file/middleware | All mutation inputs | Field errors | Invalid-input/security tests | Automated |
| NFR-OBS-001 | `request_controls` | audit/validation | Error messages | Token/header tests, Newman correlation checks | Automated |
| NFR-UX-001 | React workbench | N/A | All pages | Playwright journeys + visual inspection | Partial: formal accessibility audit pending |

Additional requirements from the master prompt are tracked honestly in IMPLEMENTATION_STATUS.md rather than marked complete without implementation.

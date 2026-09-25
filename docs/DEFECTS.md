# Observed build defects

| ID | Observed issue | Impact | Resolution / regression |
|---|---|---|---|
| BUG-001 | Ambient DATABASE_URL belonged to another environment | Local engine could not parse connection URL | Explicit project `.env` precedence; containers exclude local `.env` |
| BUG-002 | Empty data-URL CSS import failed Vite resolution | Production build failed | Removed import; production build rerun |
| BUG-003 | Accessible field name included helper text/select options | Browser could not target exact document label | Unique input IDs, explicit labels and separate descriptions; upload journey rerun |
| BUG-004 | E2E assumed seeded case was on first paginated page | Case navigation test timed out | Search reference before selection; real pagination preserved |
| BUG-005 | Validation reuse after unchanged resubmission left case submitted | Idempotent result could stall review | Reused result restores validation outcome and audits reuse; regression added |
| BUG-006 | Required Postman tool introduced vulnerable transitive dependencies | Development-tool security findings | Isolated package, compatible patched overrides; remaining exceptions documented |

These are development findings from this implementation, not claims about production incidents or customers.

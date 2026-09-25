# Interview guide

**Why PostgreSQL?** Relational integrity, transactions, row locks and mature operational tooling suit evidence and approvals. SQLite is only a convenient local/testing profile; PostgreSQL must receive its own deployment and concurrency validation.

**Why FastAPI?** Explicit request schemas, dependency-based authorization and generated API documentation keep the service boundary understandable and testable.

**Why a separate rule engine?** Amount/date/evidence logic is deterministic and testable without HTTP or database setup. Each result explains expected versus actual evidence and policy version.

**Why a state machine?** Workflow permissions alone do not express valid order. An authorized checker still cannot move a draft straight to approved.

**Why maker-checker?** Independent actors reduce unilateral decision risk. The check uses historical actor IDs, not only current role labels, so promoting a maker does not authorize self-approval.

**How are duplicates and races prevented?** Version counters, transaction locks and unique constraints work together. Input fingerprints reuse validation. Duplicate file bytes and duplicate logical document versions are constrained in SQL.

**How is IDOR prevented?** Every derived object must lead back to an LC checked through the central ownership/assignment scope. UUID obscurity is not the control.

**How are uploads secured?** Enforce raw body/file caps, allowlisted extension/signature agreement, active-content rejection, hash, UUID-keyed database storage, version preservation and scoped attachment downloads. Production still needs real antivirus/CDR and parser isolation.

**What does audit integrity prove?** It detects inconsistency relative to the currently stored chain/head. It cannot resist a database superuser who rewrites every event and the head; immutable external anchoring is the next step.

**Why not let AI approve?** Approval authority belongs to authenticated accountable humans under deterministic workflow controls. There is no AI provider in this build. Future assistance must be labeled and cannot change approval privileges.

**How are decisions reproducible?** Store the terms, document versions/hashes, effective date, rule configuration versions, engine version and results in one snapshot. Retain the historical source release to rerun exact semantics.

**Why synthetic data and API-first design?** Synthetic data makes safe reproducible demonstrations possible. The API exposes the actual business controls to tests and alternate clients instead of burying them in React.

**How does notification reliability work?** Persist the in-app record and outbox in the same business transaction. Retry the mock adapter a bounded number of times; failed work remains visible rather than looping indefinitely.

**How are rules tested?** Every rule family has a negative path; sensitive monetary/date boundaries have exact-edge parametrization; API tests prove enforcement at workflow boundaries. The browser verifies the connected journey.

**What would change at scale?** PostgreSQL operations/HA, secure object storage, distributed admission controls/workers, enterprise IAM, external audit anchoring, asynchronous validation/reporting, materialized analytics and bank-specific policy governance. Do not claim these exist merely because an architecture diagram mentions them.

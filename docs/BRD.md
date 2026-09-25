# Business requirements document

## Problem and outcomes

Documentary-credit review is error prone when monetary terms, dates, shipment evidence and human decisions are scattered. LC-Verify brings these into one traceable synthetic case. Success means a reviewer can explain which term failed, which document caused the result, who decided what, and why the final checker was permitted to approve.

Stakeholders: trade analysts, compliance reviewers, senior checkers, managers, auditors, executives, administrators, QA and security reviewers. The demo contains no real customers, accounts or confidential documents.

## Scope and acceptance criteria

| Business requirement | Acceptance criterion |
|---|---|
| BR-01 Reliable documentary checks | Exact tolerance passes; 0.01 above fails; absent evidence is visible |
| BR-02 Explainability | Every rule has an ID, version, expected/actual values, explanation and evidence |
| BR-03 Segregation of duties | Maker/submitter/reviewer cannot be final checker, even after role change |
| BR-04 Exception accountability | A waiver requires authorized actor, reason and preserved system result |
| BR-05 Auditability | Business mutations and exports produce chain-linked audit events |
| BR-06 Operational visibility | Metrics, queues and SLA states derive from persisted case data |
| BR-07 Safe demonstration | Demo seed is synthetic; external email suppressed; no real credentials |
| BR-08 Reproducible QA | Rule, API, security and browser tests run using deterministic fixtures |

Assumptions: one synthetic organization; analyst ownership and explicit reviewer assignment; no sanctions or legal determination; no FX aggregation; same-day effective validation for final decisions. Consignee matching and insurance rules are simplified demo policy, not a universally correct banking interpretation.

Constraints: local deployment; bounded file sizes; no external OCR; no identity-provider integration. Risks include incorrect interpretation if demo rules are mistaken for bank policy, privileged database tampering, and inappropriate exposure of local credentials. These are addressed through explicit disclaimers and production-gap documentation.

Future scope: formal policy signoff, tenant isolation, enterprise IAM, malware-scanning gateway, scalable artifact storage, immutable logging, distributed workers, verified production recovery and bank-specific review controls.

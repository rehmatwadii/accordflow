# Guided demo

Start the app and read `.demo-credentials.json` for the locally generated password. Only synthetic identities and documents belong in this workspace.

## Existing four-discrepancy scenario

1. Sign in as analyst. Observe dashboard values computed from the database.
2. Open LC workbench and search `01042`; open the seeded case. It contains invoice amount, currency, shipment date and packing-quantity findings.
3. Open Validation and Compare: inspect expected/actual values, rule version, explanation and evidence.
4. Open Risk: the four findings contribute 15 + 15 + 15 + 8 = 53. Try a hypothetical invoice amount. Arithmetic may become a separate failure; simulation does not silently correct other fields.
5. Sign out and sign in as reviewer. Open the assigned case and Start Review. Add an investigation note; acknowledge a finding or escalate it. Use Request Information when evidence needs correction.
6. Sign in as analyst. Upload corrected same-type JSON files using the upload dialog's matching samples. Every upload creates a new version; duplicate bytes are rejected.
7. Resubmit and Run Validation. Corrected historical findings remain visible as resolved/superseded. A new input snapshot explains the new result.
8. Sign in as reviewer. Start Review, inspect the evidence and complete every checklist item. Complete Review, then Request Approval.
9. Sign in as checker. Review terms/results/decisions and Approve with a reason. A maker or reviewer cannot perform this final action.
10. Export the compliance PDF and inspect Workflow/Audit. Sign in as auditor to Verify Audit Integrity.

## Fresh clean-credit journey

1. Analyst → New LC case. Use synthetic names, keep coherent amount/quantity/price and select FOB for the simplest four-document scenario.
2. Documents → Upload document → Download matching sample. Upload the saved sample for invoice, bill of lading, packing list and certificate of origin. JSON extracts automatically; PDF/image fields require manual input.
3. Submit with a reason, then Run Validation. All applicable checks should pass if terms/dates remain coherent.
4. Reviewer → Start Review → checklist → Complete Review → Request Approval.
5. Checker → Approve. Auditor verifies chain. Dashboard counts update from the saved state.

## Authorized exception

The seeded amount-only case can demonstrate a noncritical waiver: reviewer starts review; manager records WAIVED with a supporting reason; system FAIL and risk remain visible; reviewer completes the checklist; a separate checker decides. Missing documents, expired credits and critical findings cannot be waived. Waiving a finding does not constitute legal/bank-policy acceptance.

## Governance

Administrator can configure rule severity/enabled status with reason/version, modify role/active state (revoking sessions), configure new-case SLA hours and run a worker cycle. Administrators have no business approval privilege. Auditor access is read-only except nonmutating integrity verification; exports are audited.

Worker cycles create SLA notices and operational security signals from repeated login failures/replay events. Mock email never sends externally. Advanced AI/OCR/MFA are not presented as working features.

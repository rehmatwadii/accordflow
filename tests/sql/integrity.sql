-- All anomaly queries should return zero rows. PostgreSQL; read-only.
SELECT d.id FROM documents d LEFT JOIN lcs l ON d.lc_id=l.id WHERE l.id IS NULL;
SELECT v.id FROM validation_runs v LEFT JOIN lcs l ON v.lc_id=l.id WHERE l.id IS NULL;
SELECT d.id FROM discrepancies d LEFT JOIN validation_runs v ON d.run_id=v.id WHERE v.id IS NULL;
SELECT lc_id,type,version,COUNT(*) FROM documents GROUP BY lc_id,type,version HAVING COUNT(*) > 1;
SELECT lc_id,version,COUNT(*) FROM lc_versions GROUP BY lc_id,version HAVING COUNT(*) > 1;
SELECT id FROM lcs WHERE risk_score < 0 OR risk_score > 100;
SELECT id FROM lcs WHERE status NOT IN ('DRAFT','SUBMITTED','DOCUMENTS_PENDING','VALIDATION_IN_PROGRESS','VALIDATION_COMPLETED','DISCREPANCIES_FOUND','UNDER_REVIEW','ADDITIONAL_INFORMATION_REQUIRED','REVIEW_COMPLETED','PENDING_CHECKER','APPROVED','REJECTED','ESCALATED','CLOSED');
SELECT a.id FROM approvals a JOIN lcs l ON l.id=a.lc_id WHERE a.action='APPROVE' AND a.actor_id IN (l.created_by,l.submitted_by,l.reviewed_by);
SELECT h.id FROM audit_head h WHERE h.sequence <> (SELECT COUNT(*) FROM audit_events);

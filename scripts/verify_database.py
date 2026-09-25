from sqlalchemy import text

from backend.app.audit import verify
from backend.app.db import SessionLocal, engine

queries = [
    "SELECT COUNT(*) FROM documents d LEFT JOIN lcs l ON d.lc_id=l.id WHERE l.id IS NULL",
    "SELECT COUNT(*) FROM discrepancies d LEFT JOIN validation_runs v ON d.run_id=v.id WHERE v.id IS NULL",
    "SELECT COUNT(*) FROM lcs WHERE risk_score < 0 OR risk_score > 100",
    "SELECT COUNT(*) FROM approvals a JOIN lcs l ON l.id=a.lc_id WHERE a.action='APPROVE' AND a.actor_id IN (l.created_by,l.submitted_by,l.reviewed_by)",
]
with SessionLocal() as db:
    if engine.dialect.name == "sqlite":
        assert db.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        assert not db.execute(text("PRAGMA foreign_key_check")).all()
    for query in queries:
        assert db.execute(text(query)).scalar_one() == 0
    result = verify(db)
    assert result["status"] == "PASS"
    print(f"Database constraints and audit integrity PASS ({result['checked']} audit events)")

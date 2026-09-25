from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from sqlalchemy import func, select

from backend.app.audit import verify
from backend.app.jobs import deliver, monitor
from backend.app.models import AuditEvent, LC, OutboxEvent, now
from scripts.seed import demo_terms
from tests.integration.test_workflow import action, make_case


def test_monitor_is_idempotent_and_provider_retries_are_bounded(system, login):
    client, factory, _ = system
    headers = login("analyst")
    lc = client.post(
        "/api/v1/lcs", headers=headers, json={"title": "Synthetic SLA probe", "terms": demo_terms()}
    ).json()
    with factory() as db:
        db.get(LC, lc["id"]).due_at = now() - timedelta(hours=1)
        assert monitor(db)["sla_events"] == 1
        assert monitor(db)["sla_events"] == 0
        db.commit()

    class FailedProvider:
        def send(self, *args, **kwargs):
            raise RuntimeError("Controlled provider outage")

    with factory() as db:
        for attempt in range(3):
            for event in db.scalars(select(OutboxEvent).where(OutboxEvent.state.in_(["PENDING", "RETRY"]))):
                event.next_attempt = now() - timedelta(seconds=1)
            deliver(db, FailedProvider())
        assert db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.state == "DEAD")) > 0
        assert deliver(db)["delivered"] == 0
        db.commit()


def test_concurrent_submission_has_one_winner(system, login):
    client, factory, _ = system
    headers = login("analyst")
    lc = client.post(
        "/api/v1/lcs", headers=headers, json={"title": "Synthetic concurrency probe", "terms": demo_terms()}
    ).json()
    barrier = Barrier(2)

    def submit(_):
        barrier.wait()
        return action(client, headers, lc, "SUBMIT").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))
    assert statuses.count(200) == 1
    assert all(status in {200, 409, 503} for status in statuses)
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "SUBMIT", AuditEvent.entity_id == lc["id"])
            )
            == 1
        )
        assert verify(db)["status"] == "PASS"


def test_revalidation_resolves_corrected_findings_and_reuse_moves_state(system, login):
    client, _, _ = system
    analyst = login("analyst")
    lc = make_case(client, analyst, "amount")
    lc = action(client, analyst, lc, "SUBMIT").json()
    path = "/api/v1/lcs/" + lc["id"]
    first = client.post(path + "/validation", headers=analyst).json()
    reviewer = login("reviewer")
    lc = client.get(path, headers=reviewer).json()
    lc = action(client, reviewer, lc, "START_REVIEW").json()
    lc = action(client, reviewer, lc, "REQUEST_INFORMATION").json()
    lc = action(client, analyst, lc, "SUBMIT").json()
    reused = client.post(path + "/validation", headers=analyst).json()
    assert reused["id"] == first["id"]
    assert client.get(path, headers=analyst).json()["status"] == "DISCREPANCIES_FOUND"

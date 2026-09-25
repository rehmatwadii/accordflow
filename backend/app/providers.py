from typing import Protocol

from .models import Notification, OutboxEvent, uid


class NotificationProvider(Protocol):
    def send(self, db, user_id: str, lc_id: str, message: str): ...


class InAppNotificationProvider:
    def send(self, db, user_id, lc_id, message):
        db.add(Notification(user_id=user_id, lc_id=lc_id, message=message))
        db.add(
            OutboxEvent(
                event_key=uid(),
                event_type="MOCK_EMAIL",
                payload={"user_id": user_id, "lc_id": lc_id, "message": message},
            )
        )


class MockEmailProvider:
    def send(self, db, user_id, lc_id, message):
        return {"status": "SUPPRESSED", "provider": "mock", "reason": "Demo mode never transmits email"}


notifications = InAppNotificationProvider()

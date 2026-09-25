"""Generate local demo secrets without printing or committing them."""

import json
import secrets
from pathlib import Path

from dotenv import dotenv_values, set_key


def configure():
    env = Path(".env")
    if not env.exists():
        env.write_text(Path(".env.example").read_text(), encoding="utf-8")
    values = dotenv_values(env)
    credentials = Path(".demo-credentials.json")
    previous = json.loads(credentials.read_text()) if credentials.exists() else {}
    password = (
        values.get("DEMO_PASSWORD") or previous.get("password") or "Demo-" + secrets.token_urlsafe(18) + "7aA"
    )
    if not values.get("DEMO_PASSWORD"):
        set_key(str(env), "DEMO_PASSWORD", password)
    if not values.get("POSTGRES_PASSWORD"):
        set_key(str(env), "POSTGRES_PASSWORD", secrets.token_hex(24))
    from scripts.seed import ACCOUNTS

    credentials.write_text(
        json.dumps(
            {
                "warning": "LOCAL DEMO ONLY — DO NOT COMMIT",
                "password": password,
                "accounts": [a[0] + "@lcverify.demo" for a in ACCOUNTS],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Local demo configuration ready. Credentials: .demo-credentials.json")


if __name__ == "__main__":
    configure()

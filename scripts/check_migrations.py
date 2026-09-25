"""Upgrade, downgrade and recreate a disposable SQLite schema, never the working database."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="lcverify-migration-") as temporary:
    directory = Path(temporary)
    env_file = directory / "migration.env"
    env_file.write_text(
        "APP_ENV=test\nDATABASE_URL=sqlite:///" + (directory / "migration.db").as_posix() + "\n"
    )
    environment = {**os.environ, "LCV_ENV_FILE": str(env_file)}
    for args in [("upgrade", "head"), ("check",), ("downgrade", "base"), ("upgrade", "head")]:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args], env=environment, capture_output=True, text=True
        )
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
    print("Disposable migration upgrade/check/downgrade/re-upgrade PASS")

import json
import os
import subprocess
from pathlib import Path


def main():
    credentials = json.loads(Path(".demo-credentials.json").read_text())
    env_path = Path("data/newman-private-environment.json")
    env_path.write_text(
        json.dumps(
            {
                "values": [
                    {
                        "key": "base_url",
                        "value": os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000"),
                        "enabled": True,
                    },
                    {"key": "demo_password", "value": credentials["password"], "enabled": True},
                ]
            }
        )
    )
    try:
        result = subprocess.run(
            [
                "node",
                "postman/node_modules/newman/bin/newman.js",
                "run",
                "postman/AccordFlow.postman_collection.json",
                "-e",
                str(env_path),
                "--reporters",
                "cli,junit",
                "--reporter-junit-export",
                "data/newman-results.xml",
                "--bail",
            ],
            check=False,
        )
    finally:
        env_path.unlink(missing_ok=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

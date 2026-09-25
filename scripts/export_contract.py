import json
from pathlib import Path

from backend.app.main import app

Path("docs").mkdir(exist_ok=True)
Path("docs/openapi.json").write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print("Exported current OpenAPI contract")

"""Run and preserve the isolated tool scan, rejecting findings outside a dated exception baseline."""

import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

baseline = json.loads(Path("postman/audit-baseline.json").read_text())
# Resolve npm's executable with shutil; run its JavaScript CLI to avoid shell interpolation on Windows.
node = shutil.which("node")
npm = shutil.which("npm")
if not node or not npm:
    raise SystemExit("Node/npm are required")
if Path(npm).suffix.lower() == ".cmd":
    npm_cli = Path(npm).parent / "node_modules/npm/bin/npm-cli.js"
    command = [node, str(npm_cli), "audit", "--json"]
else:
    command = [npm, "audit", "--json"]
result = subprocess.run(command, cwd="postman", capture_output=True, text=True)
report = json.loads(result.stdout)
Path("data").mkdir(exist_ok=True)
Path("data/newman-audit.json").write_text(json.dumps(report, indent=2))
ids = set()
for vulnerability in report.get("vulnerabilities", {}).values():
    for source in vulnerability.get("via", []):
        if isinstance(source, dict):
            match = re.search(r"GHSA-[a-z0-9-]+", source.get("url", ""))
            ids.add(match.group(0) if match else source.get("url", "unknown"))
unexpected = ids - set(baseline["allowed_advisory_ids"])
if unexpected or date.today() > date.fromisoformat(baseline["expires"]):
    raise SystemExit("Tool dependency review required: unexpected advisory or expired baseline")
print(
    f"Isolated Newman scan: {len(ids)} acknowledged upstream advisories; no unreviewed findings. See docs/SECURITY_RESULTS.md."
)

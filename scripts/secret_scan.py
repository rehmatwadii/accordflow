"""Scan publishable Git files without printing matching credential values."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    command = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
        if args.staged
        else ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    names = sorted(set(filter(None, subprocess.check_output(command).decode().split("\0"))))
    patterns = [
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
        re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
        re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b"),
        re.compile(rb"\bK[0-9]{12,20}\b"),
    ]
    known = []
    for key, value in dotenv_values(".env").items():
        if (
            value
            and len(value) >= 8
            and any(word in key.upper() for word in ("KEY", "PASSWORD", "SECRET", "TOKEN"))
        ):
            known.append(value.encode())
    credentials = Path(".demo-credentials.json")
    if credentials.exists():
        password = json.loads(credentials.read_text(encoding="utf-8")).get("password")
        if password:
            known.append(password.encode())
    findings = []
    for name in names:
        path = Path(name)
        forbidden = (
            (path.name.startswith(".env") and path.name != ".env.example")
            or path.name == ".demo-credentials.json"
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3", ".pdf"}
            or any(part in {"data", "uploads", "backups", "node_modules", ".venv"} for part in path.parts)
        )
        if forbidden:
            findings.append(f"{name}: private/generated file")
            continue
        if args.staged:
            content = subprocess.check_output(["git", "show", ":" + name])
        elif path.is_file():
            content = path.read_bytes()
        else:
            continue
        if any(pattern.search(content) for pattern in patterns) or any(value in content for value in known):
            findings.append(f"{name}: possible credential")
    if findings:
        raise SystemExit("Publishing blocked by secret scan:\n" + "\n".join(findings))
    print(
        f"Scanned {len(names)} Git files: no supported patterns or known local credentials found. Heuristic checks are not a guarantee."
    )


if __name__ == "__main__":
    main()

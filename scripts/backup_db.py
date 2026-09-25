"""Local SQLite online backup; PostgreSQL uses pg_dump via docker compose."""

import argparse
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise SystemExit("Destination already exists; choose a new backup filename")
    source = Path("data/lcverify.db").resolve()
    if not source.exists():
        raise SystemExit("Local demo database does not exist")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
        with sqlite3.connect(args.destination) as dest:
            src.backup(dest)
    print("Backup completed. Protect the backup like the source database.")


if __name__ == "__main__":
    main()

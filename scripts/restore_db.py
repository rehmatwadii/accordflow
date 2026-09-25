import argparse
import shutil
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Restore into a NEW database path, never overwrite a running database"
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if not args.backup.is_file() or args.destination.exists():
        raise SystemExit("Backup must exist and destination must be a new file")
    with sqlite3.connect(f"file:{args.backup.resolve().as_posix()}?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit("Backup failed integrity verification")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.backup, args.destination)
    print("Restored to the new path. Stop the app before switching DATABASE_URL.")


if __name__ == "__main__":
    main()

import argparse
import time

from backend.app.db import SessionLocal
from backend.app.jobs import deliver, monitor


def cycle():
    with SessionLocal() as db:
        results = {**monitor(db), **deliver(db)}
        db.commit()
        return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            print(cycle(), flush=True)
        except Exception:
            print(
                "Worker cycle failed safely; transaction rolled back. Next attempt in 30 seconds.", flush=True
            )
        if args.once:
            break
        time.sleep(30)

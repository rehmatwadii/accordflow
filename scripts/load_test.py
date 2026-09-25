"""Small authenticated read-load probe; no credentials in command-line arguments."""

import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx


async def main():
    password = json.loads(Path(".demo-credentials.json").read_text())["password"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
        login = await client.post(
            "/api/v1/auth/login", json={"email": "analyst@lcverify.demo", "password": password}
        )
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        semaphore = asyncio.Semaphore(5)

        async def probe(i):
            async with semaphore:
                start = time.perf_counter()
                r = await client.get(
                    "/api/v1/lcs?page_size=12" if i % 2 else "/api/v1/reports/dashboard", headers=headers
                )
                r.raise_for_status()
                return (time.perf_counter() - start) * 1000

        samples = await asyncio.gather(*(probe(i) for i in range(50)))
        await client.post("/api/v1/auth/logout", headers=headers)
    report = {
        "requests": 50,
        "concurrency": 5,
        "mean_ms": round(statistics.mean(samples), 2),
        "p95_ms": round(sorted(samples)[47], 2),
        "max_ms": round(max(samples), 2),
        "errors": 0,
    }
    Path("data/load-results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    asyncio.run(main())

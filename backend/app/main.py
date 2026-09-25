import json
import logging
import time
from collections import defaultdict, deque
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from . import admin, auth, cases, reports
from .config import ENV, ORIGINS
from .db import get_db
from .errors import AppError
from .middleware import RequestBodyLimit
from .security import require

app = FastAPI(
    title="LC-Verify Enterprise API",
    version="1.0.0",
    description="Synthetic documentary-credit operations. No real banking data or regulatory certification.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-LCV-Client"],
    expose_headers=["X-Correlation-ID"],
)
app.add_middleware(RequestBodyLimit)
for router in (auth.router, cases.router, admin.router, reports.router):
    app.include_router(router)

log = logging.getLogger("lcverify")
RATE_BUCKETS = defaultdict(deque)
METRICS = {"requests": 0, "errors": 0, "rate_limited": 0, "latency_ms_total": 0}


def error_response(request, status, code, message, details=None):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "correlation_id": getattr(request.state, "correlation_id", "unavailable"),
            }
        },
    )


@app.middleware("http")
async def request_controls(request: Request, call_next):
    request.state.correlation_id = "LCV-REQ-" + uuid4().hex[:20].upper()
    start = time.monotonic()
    METRICS["requests"] += 1
    path = request.url.path
    response = None
    content_length = request.headers.get("content-length", "0")
    if not content_length.isdigit() or int(content_length) > 6 * 1024 * 1024:
        response = error_response(request, 413, "REQUEST_SIZE", "Request exceeds 6 MB")
    if path.startswith("/api/v1") and request.method != "OPTIONS":
        category = (
            "login"
            if path.endswith("/login")
            else "validation"
            if path.endswith("/validation")
            else "upload"
            if path.endswith("/documents")
            else "api"
        )
        limit = {"login": 15, "validation": 30, "upload": 30, "api": 600}[category]
        key = (request.client.host if request.client else "unknown", category)
        bucket = RATE_BUCKETS[key]
        while bucket and bucket[0] < start - 60:
            bucket.popleft()
        if len(bucket) >= limit:
            METRICS["rate_limited"] += 1
            response = error_response(request, 429, "RATE_LIMITED", "Too many requests. Retry in one minute")
        else:
            bucket.append(start)
    if response is None:
        try:
            response = await call_next(request)
        except Exception:
            # Do not leak exception messages, SQL parameters, secrets or filesystem paths.
            log.error(
                json.dumps({"event": "unhandled_error", "correlation_id": request.state.correlation_id})
            )
            response = error_response(request, 500, "INTERNAL_ERROR", "The request could not be completed")
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if not path.startswith("/api/docs") and not path.startswith("/api/redoc")
        else "default-src 'self' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com",
    )
    if path.startswith("/api/v1"):
        response.headers["Cache-Control"] = "no-store"
    if ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    elapsed = round((time.monotonic() - start) * 1000, 2)
    METRICS["latency_ms_total"] += elapsed
    METRICS["errors"] += int(response.status_code >= 400)
    log.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "status": response.status_code,
                "duration_ms": elapsed,
                "correlation_id": request.state.correlation_id,
            }
        )
    )
    return response


@app.exception_handler(AppError)
async def app_error(request, exc):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    details = [{"field": ".".join(map(str, e["loc"])), "type": e["type"]} for e in exc.errors()]
    return error_response(
        request, 422, "INVALID_INPUT", "Check the required fields and supported values", details
    )


@app.exception_handler(StaleDataError)
@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return error_response(
        request, 409, "CONFLICT", "A concurrent or duplicate operation was detected; refresh and retry"
    )


@app.exception_handler(OperationalError)
async def database_error(request, exc):
    return error_response(request, 503, "SERVICE_UNAVAILABLE", "Data service is temporarily unavailable")


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error_response(request, exc.status_code, "HTTP_ERROR", "Requested operation is not available")


@app.get("/health/live", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
def live():
    return {"status": "UP", "service": "lc-verify", "environment": ENV}


@app.get("/health/ready", tags=["Health"])
def ready(db=Depends(get_db)):
    db.execute(text("SELECT sequence FROM audit_head WHERE id=1")).scalar_one()
    return {"status": "READY"}


@app.get("/api/v1/metrics", tags=["Administration"])
def metrics(user=Depends(require("SYSTEM_CONFIGURE"))):
    return {
        **METRICS,
        "scope": "Current application process since start",
        "average_latency_ms": round(METRICS["latency_ms_total"] / max(METRICS["requests"], 1), 2),
    }


dist = Path("frontend/dist")
if dist.is_dir():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith(("api/", "health/")):
            raise AppError(404, "NOT_FOUND", "Endpoint not found")
        return FileResponse(dist / "index.html")

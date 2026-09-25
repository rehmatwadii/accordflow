import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.getenv("LCV_ENV_FILE", ".env"), override=True)
ENV = os.getenv("APP_ENV", "demo")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/lcverify.db")
ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
).split(",")
STORAGE = Path(os.getenv("STORAGE_PATH", "./data/documents"))
if ENV == "production":
    if not DATABASE_URL.startswith("postgresql") or not os.getenv("ALLOWED_ORIGINS"):
        raise RuntimeError("Production requires PostgreSQL and explicit HTTPS origins")
    if any(not origin.startswith("https://") for origin in ORIGINS):
        raise RuntimeError("Production origins must use HTTPS")
    if os.getenv("DEMO_PASSWORD"):
        raise RuntimeError("Demo credentials are prohibited in production")
STORAGE.mkdir(parents=True, exist_ok=True)
Path("data").mkdir(exist_ok=True)
DISCLAIMER = "SYNTHETIC DEMONSTRATION DATA — NOT FOR REAL BANKING USE"

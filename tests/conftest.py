import secrets
import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base, get_db
from backend.app.main import RATE_BUCKETS, app
from scripts.seed import initialize


@pytest.fixture(scope="session")
def baseline(tmp_path_factory):
    path = tmp_path_factory.mktemp("baseline") / "baseline.db"
    password = "Test-" + secrets.token_urlsafe(20) + "7aA"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as db:
        initialize(db, password)
        db.commit()
    engine.dispose()
    return path, password


@pytest.fixture
def system(tmp_path, baseline):
    path = tmp_path / "test.db"
    shutil.copyfile(baseline[0], path)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def pragmas(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(engine, expire_on_commit=False)

    def dependency():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = dependency
    RATE_BUCKETS.clear()
    with TestClient(app) as client:
        yield client, factory, baseline[1]
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def login(system):
    client, _, password = system

    def authenticate(role):
        response = client.post(
            "/api/v1/auth/login", json={"email": role + "@lcverify.demo", "password": password}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    return authenticate

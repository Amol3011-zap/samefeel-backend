"""Admin endpoints must reject unauthenticated callers (fail closed)."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.routes import admin


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(admin.router, prefix="/api/admin")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.count.return_value = 0
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.mark.parametrize("method,path", [("get", "/api/admin/stats"), ("post", "/api/admin/healers/1/verify")])
def test_rejects_anonymous(client, monkeypatch, method, path):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret-test-value")
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("method,path", [("get", "/api/admin/stats"), ("post", "/api/admin/healers/1/verify")])
def test_rejects_wrong_key(client, monkeypatch, method, path):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret-test-value")
    assert getattr(client, method)(path, headers={"X-Admin-Key": "nope"}).status_code == 401


def test_unset_secret_never_matches_empty_key(client, monkeypatch):
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    assert client.get("/api/admin/stats", headers={"X-Admin-Key": ""}).status_code == 401


def test_rejects_garbage_bearer(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret-test-value")
    assert client.get("/api/admin/stats", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_accepts_correct_key(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret-test-value")
    assert client.get("/api/admin/stats", headers={"X-Admin-Key": "s3cret-test-value"}).status_code == 200

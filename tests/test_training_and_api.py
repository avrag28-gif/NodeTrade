import time

import pandas as pd
from fastapi.testclient import TestClient

from nodetrade.api import LicenseStore, create_app
from nodetrade.training import ModelGate, EvaluationResult, validate_dataset


def candles(n=220):
    ts = pd.date_range("2026-01-01", periods=n, freq="min")
    close = pd.Series(range(100, 100 + n), dtype=float)
    return pd.DataFrame({"timestamp": ts, "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1000})


def test_dataset_validation():
    validate_dataset(candles())


def test_dataset_rejects_short_input():
    try:
        validate_dataset(candles(50))
        assert False
    except ValueError as exc:
        assert "at least 200" in str(exc)


def test_model_gate_keeps_failed_candidates_out():
    gate = ModelGate()
    assert not gate.approve(EvaluationResult("failed", 1000, {"oos_accuracy": 0.99}))
    assert not gate.approve(EvaluationResult("passed", 50, {"oos_accuracy": 0.99}))


def test_api_auth_and_health(tmp_path):
    secret = "test-secret"
    store = LicenseStore(tmp_path / "db.sqlite")
    store.provision("123", "key", secret)
    client = TestClient(create_app(license_store=store, license_secret=secret))
    assert client.get("/health").status_code == 200
    assert client.post("/v1/heartbeat", json={"account_id": "123", "symbol": "XAUUSD", "terminal_time": int(time.time())}).status_code == 401
    token = client.post("/v1/activate", json={"account_id": "123", "activation_key": "key"}).json()["token"]
    assert client.post("/v1/heartbeat", headers={"Authorization": f"Bearer {token}"}, json={"account_id": "123", "symbol": "XAUUSD", "terminal_time": int(time.time())}).status_code == 200


def test_event_idempotency(tmp_path):
    secret = "test-secret"
    store = LicenseStore(tmp_path / "db.sqlite")
    store.provision("123", "key", secret)
    client = TestClient(create_app(license_store=store, license_secret=secret))
    token = client.post("/v1/activate", json={"account_id": "123", "activation_key": "key"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = {"account_id":"123","event_id":"evt-1","symbol":"XAUUSD","event_type":"DEAL_ADD","time":int(time.time())}
    assert client.post("/v1/trade-events", headers=headers, json=body).json()["accepted"] is True
    assert client.post("/v1/trade-events", headers=headers, json=body).json()["duplicate"] is True

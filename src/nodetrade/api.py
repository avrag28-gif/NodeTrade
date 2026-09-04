from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine import NodeTradeEngine
from .types import Signal


@dataclass(frozen=True)
class License:
    account_id: str
    key_hash: str
    enabled: bool = True
    expires_at: int | None = None

    def active(self, now: int | None = None) -> bool:
        if not self.enabled:
            return False
        return self.expires_at is None or (now or int(time.time())) < self.expires_at


class LicenseStore:
    """Small SQLite license store; plaintext activation keys are never persisted."""

    def __init__(self, path: str | os.PathLike[str] = "nodetrade.db") -> None:
        self.path = str(path)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS licenses ("
                "account_id TEXT PRIMARY KEY, key_hash TEXT NOT NULL, "
                "enabled INTEGER NOT NULL DEFAULT 1, expires_at INTEGER)"
            )

    def _connect(self) -> sqlite3.Connection:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    @staticmethod
    def _hash(account_id: str, activation_key: str, secret: str) -> str:
        msg = f"{account_id}:{activation_key}".encode()
        return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()

    def provision(self, account_id: str, activation_key: str, secret: str, expires_at: int | None = None) -> None:
        digest = self._hash(account_id, activation_key, secret)
        with self._connect() as db:
            db.execute(
                "INSERT INTO licenses(account_id,key_hash,enabled,expires_at) VALUES(?,?,1,?) "
                "ON CONFLICT(account_id) DO UPDATE SET key_hash=excluded.key_hash, enabled=1, expires_at=excluded.expires_at",
                (account_id, digest, expires_at),
            )

    def verify(self, account_id: str, activation_key: str, secret: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT key_hash,enabled,expires_at FROM licenses WHERE account_id=?",
                (account_id,),
            ).fetchone()
        if row is None or not bool(row[1]):
            return False
        if row[2] is not None and int(time.time()) >= int(row[2]):
            return False
        expected = self._hash(account_id, activation_key, secret)
        return hmac.compare_digest(str(row[0]), expected)


def create_app(
    engine: NodeTradeEngine | None = None,
    license_store: LicenseStore | None = None,
    license_secret: str | None = None,
) -> Any:
    """Create the HTTP API used by the MT5 EA.

    FastAPI is imported lazily so the research/core package remains usable without
    installing server dependencies. Production deployments should put this service
    behind HTTPS and a reverse proxy/rate limiter.
    """
    try:
        from fastapi import FastAPI, Header, HTTPException
        from pydantic import BaseModel, Field
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Install the 'server' extra to run NodeTrade API") from exc

    class Candle(BaseModel):
        time: int
        open: float = Field(gt=0)
        high: float = Field(gt=0)
        low: float = Field(gt=0)
        close: float = Field(gt=0)
        volume: float = Field(ge=0)

    class AnalyzeRequest(BaseModel):
        account_id: str = Field(min_length=1, max_length=128)
        activation_key: str = Field(min_length=1, max_length=256)
        symbol: str = Field(min_length=1, max_length=64)
        bid: float = Field(gt=0)
        ask: float = Field(gt=0)
        equity: float = Field(gt=0)
        day_start_equity: float | None = Field(default=None, gt=0)
        candles: list[Candle] = Field(min_length=100, max_length=5000)

    class HealthResponse(BaseModel):
        status: str
        version: str

    app = FastAPI(title="NodeTrade API", version="0.1.0")
    eng = engine or NodeTradeEngine()
    store = license_store or LicenseStore(os.getenv("NODETRADE_DB", "nodetrade.db"))
    secret = license_secret or os.getenv("NODETRADE_LICENSE_SECRET")
    if not secret:
        raise RuntimeError("NODETRADE_LICENSE_SECRET must be set")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version="0.1.0")

    @app.post("/v1/analyze")
    def analyze(req: AnalyzeRequest, x_request_id: str | None = Header(default=None)) -> dict[str, Any]:
        if not store.verify(req.account_id, req.activation_key, secret):
            raise HTTPException(status_code=401, detail="unauthorized")
        if req.ask < req.bid:
            raise HTTPException(status_code=422, detail="ask must be >= bid")

        import pandas as pd

        frame = pd.DataFrame([c.model_dump() for c in req.candles]).rename(columns={"time": "timestamp"})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
        signal: Signal = eng.analyze(
            frame,
            bid=req.bid,
            ask=req.ask,
            equity=req.equity,
            day_start_equity=req.day_start_equity,
        )
        payload = signal.to_dict()
        payload.update({"symbol": req.symbol, "request_id": x_request_id or secrets.token_hex(8)})
        return payload

    return app

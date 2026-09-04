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
        now = int(time.time()) if now is None else now
        return self.enabled and (self.expires_at is None or now < self.expires_at)


class LicenseStore:
    """SQLite store for licenses, sessions and idempotent event keys."""

    def __init__(self, path: str | os.PathLike[str] = "nodetrade.db") -> None:
        self.path = str(path)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS licenses (account_id TEXT PRIMARY KEY, key_hash TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, expires_at INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS idempotency (account_id TEXT NOT NULL, event_key TEXT NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY(account_id,event_key))")

    def _connect(self) -> sqlite3.Connection:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def _hash(account_id: str, activation_key: str, secret: str) -> str:
        return hmac.new(secret.encode(), f"{account_id}:{activation_key}".encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def provision(self, account_id: str, activation_key: str, secret: str, expires_at: int | None = None) -> None:
        digest = self._hash(account_id, activation_key, secret)
        with self._connect() as db:
            db.execute("INSERT INTO licenses(account_id,key_hash,enabled,expires_at) VALUES(?,?,1,?) ON CONFLICT(account_id) DO UPDATE SET key_hash=excluded.key_hash, enabled=1, expires_at=excluded.expires_at", (account_id, digest, expires_at))

    def verify(self, account_id: str, activation_key: str, secret: str) -> bool:
        with self._connect() as db:
            row = db.execute("SELECT key_hash,enabled,expires_at FROM licenses WHERE account_id=?", (account_id,)).fetchone()
        if row is None or not bool(row[1]): return False
        if row[2] is not None and int(time.time()) >= int(row[2]): return False
        return hmac.compare_digest(str(row[0]), self._hash(account_id, activation_key, secret))

    def create_session(self, account_id: str, activation_key: str, secret: str, ttl_seconds: int = 3600) -> str | None:
        if not self.verify(account_id, activation_key, secret): return None
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._connect() as db:
            db.execute("INSERT INTO sessions(token_hash,account_id,created_at,last_seen) VALUES(?,?,?,?)", (self._token_hash(token), account_id, now, now))
        return token

    def authenticate(self, token: str, account_id: str, max_age: int = 3600) -> bool:
        now = int(time.time())
        token_hash = self._token_hash(token)
        with self._connect() as db:
            row = db.execute("SELECT created_at FROM sessions WHERE token_hash=? AND account_id=?", (token_hash, account_id)).fetchone()
            if row is None: return False
            if now - int(row[0]) >= max_age:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
                return False
            db.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, token_hash))
        return True

    def accept_event_once(self, account_id: str, event_key: str) -> bool:
        try:
            with self._connect() as db:
                db.execute("INSERT INTO idempotency(account_id,event_key,created_at) VALUES(?,?,?)", (account_id, event_key, int(time.time())))
            return True
        except sqlite3.IntegrityError:
            return False


def create_app(engine: NodeTradeEngine | None = None, license_store: LicenseStore | None = None, license_secret: str | None = None) -> Any:
    try:
        from fastapi import FastAPI, Header, HTTPException
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("Install the 'server' extra to run NodeTrade API") from exc

    class Candle(BaseModel):
        time: int
        open: float = Field(gt=0)
        high: float = Field(gt=0)
        low: float = Field(gt=0)
        close: float = Field(gt=0)
        volume: float = Field(ge=0)

    class ActivateRequest(BaseModel):
        account_id: str = Field(min_length=1, max_length=128)
        activation_key: str = Field(min_length=1, max_length=256)

    class AnalyzeRequest(BaseModel):
        account_id: str = Field(min_length=1, max_length=128)
        symbol: str = Field(min_length=1, max_length=64)
        bid: float = Field(gt=0)
        ask: float = Field(gt=0)
        equity: float = Field(gt=0)
        day_start_equity: float | None = Field(default=None, gt=0)
        tick_size: float = Field(gt=0)
        tick_value: float = Field(gt=0)
        volume_min: float = Field(gt=0)
        volume_max: float = Field(gt=0)
        volume_step: float = Field(gt=0)
        candles: list[Candle] = Field(min_length=100, max_length=5000)

    class HeartbeatRequest(BaseModel):
        account_id: str = Field(min_length=1, max_length=128)
        symbol: str = Field(min_length=1, max_length=64)
        terminal_time: int = Field(gt=0)

    class TradeEvent(BaseModel):
        account_id: str = Field(min_length=1, max_length=128)
        event_id: str = Field(min_length=1, max_length=128)
        symbol: str = Field(min_length=1, max_length=64)
        event_type: str = Field(min_length=1, max_length=64)
        ticket: int = Field(default=0, ge=0)
        deal: int = Field(default=0, ge=0)
        order: int = Field(default=0, ge=0)
        volume: float = Field(default=0, ge=0)
        price: float = Field(default=0, ge=0)
        profit: float = 0
        time: int = Field(gt=0)
        payload: dict[str, Any] = Field(default_factory=dict)

    class ReconcileRequest(BaseModel):
        account_id: str = Field(min_length=1, max_length=128)
        symbol: str = Field(min_length=1, max_length=64)
        positions: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
        equity: float = Field(gt=0)
        terminal_time: int = Field(gt=0)

    app = FastAPI(title="NodeTrade API", version="0.3.0")
    eng = engine or NodeTradeEngine()
    store = license_store or LicenseStore(os.getenv("NODETRADE_DB", "nodetrade.db"))
    secret = license_secret or os.getenv("NODETRADE_LICENSE_SECRET")
    if not secret: raise RuntimeError("NODETRADE_LICENSE_SECRET must be set")

    def require_session(account_id: str, authorization: str | None) -> None:
        if not authorization or not authorization.startswith("Bearer ") or not store.authenticate(authorization[7:].strip(), account_id):
            raise HTTPException(status_code=401, detail="invalid or expired session")

    @app.get("/health")
    def health() -> dict[str, str]: return {"status": "ok", "version": "0.3.0"}

    @app.post("/v1/activate")
    def activate(req: ActivateRequest) -> dict[str, Any]:
        token = store.create_session(req.account_id, req.activation_key, secret)
        if token is None: raise HTTPException(status_code=401, detail="activation rejected")
        return {"account_id": req.account_id, "token": token, "expires_in": 3600}

    @app.post("/v1/heartbeat")
    def heartbeat(req: HeartbeatRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_session(req.account_id, authorization)
        return {"ok": True, "server_time": int(time.time()), "account_id": req.account_id}

    @app.post("/v1/analyze")
    def analyze(req: AnalyzeRequest, authorization: str | None = Header(default=None), x_request_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_session(req.account_id, authorization)
        if req.ask < req.bid: raise HTTPException(status_code=422, detail="ask must be >= bid")
        import pandas as pd
        frame = pd.DataFrame([c.model_dump() for c in req.candles]).rename(columns={"time": "timestamp"})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
        signal: Signal = eng.analyze(frame, bid=req.bid, ask=req.ask, equity=req.equity, day_start_equity=req.day_start_equity)
        payload = signal.to_dict()
        volume = 0.0
        if signal.action.value in {"long", "short"} and signal.entry and signal.stop:
            stop_distance = abs(signal.entry - signal.stop)
            loss_per_lot = stop_distance / req.tick_size * req.tick_value
            risk_cash = req.equity * eng.config.risk.risk_per_trade
            if loss_per_lot > 0:
                volume = min(req.volume_max, risk_cash / loss_per_lot)
                volume = max(req.volume_min, (volume // req.volume_step) * req.volume_step)
                volume = round(volume, 8) if volume >= req.volume_min else 0.0
        payload.update({"symbol": req.symbol, "request_id": x_request_id or secrets.token_hex(8), "server_time": int(time.time()), "volume": volume})
        return payload

    @app.post("/v1/trade-events")
    def trade_event(req: TradeEvent, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_session(req.account_id, authorization)
        accepted = store.accept_event_once(req.account_id, req.event_id)
        return {"accepted": accepted, "duplicate": not accepted, "server_time": int(time.time())}

    @app.post("/v1/reconcile")
    def reconcile(req: ReconcileRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_session(req.account_id, authorization)
        return {"ok": True, "server_time": int(time.time()), "account_id": req.account_id, "symbol": req.symbol, "positions_received": len(req.positions), "safe_to_trade": True}

    return app

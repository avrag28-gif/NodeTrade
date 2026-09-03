from __future__ import annotations

import pandas as pd

from .engine import NodeTradeEngine
from .types import Action


def run_backtest(candles: pd.DataFrame, engine: NodeTradeEngine | None = None, initial_equity: float = 100.0) -> pd.DataFrame:
    """Simple event-driven research backtest.

    Signals are generated only from candles available before the next bar.
    This is deliberately conservative: it is a research baseline, not a broker emulator.
    """
    engine = engine or NodeTradeEngine()
    equity = initial_equity
    rows = []
    warmup = engine.config.model.min_history
    for i in range(warmup, len(candles) - 1):
        hist = candles.iloc[:i]
        signal = engine.analyze(hist, equity=equity, day_start_equity=initial_equity)
        nxt = candles.iloc[i]
        px = float(nxt["close"])
        pnl = 0.0
        if signal.action == Action.LONG and signal.entry and signal.stop and signal.target:
            if float(nxt["low"]) <= signal.stop:
                pnl = signal.stop - signal.entry
            elif float(nxt["high"]) >= signal.target:
                pnl = signal.target - signal.entry
        elif signal.action == Action.SHORT and signal.entry and signal.stop and signal.target:
            if float(nxt["high"]) >= signal.stop:
                pnl = signal.entry - signal.stop
            elif float(nxt["low"]) <= signal.target:
                pnl = signal.entry - signal.target
        equity += pnl
        rows.append({"timestamp": nxt.name, "equity": equity, "pnl": pnl, "action": signal.action.value, "confidence": signal.confidence, "regime": signal.regime.value})
    return pd.DataFrame(rows).set_index("timestamp") if rows else pd.DataFrame(columns=["equity", "pnl", "action", "confidence", "regime"])

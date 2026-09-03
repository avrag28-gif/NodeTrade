from __future__ import annotations

import pandas as pd

from .engine import NodeTradeEngine
from .types import Action


def run_backtest(
    candles: pd.DataFrame,
    engine: NodeTradeEngine | None = None,
    initial_equity: float = 100.0,
) -> pd.DataFrame:
    """Deterministic event-driven backtest with causal sizing and conservative OHLC fills."""
    engine = engine or NodeTradeEngine()
    equity = float(initial_equity)
    rows: list[dict] = []
    warmup = engine.config.model.min_history
    for i in range(warmup, len(candles) - 1):
        hist = candles.iloc[:i]
        signal = engine.analyze(hist, equity=equity, day_start_equity=initial_equity)
        nxt = candles.iloc[i]
        pnl = 0.0
        quantity = 0.0
        outcome = "no_trade"
        if signal.action in (Action.LONG, Action.SHORT) and signal.entry and signal.stop and signal.target:
            quantity = engine.risk.size(equity, signal.entry, signal.stop)
            if quantity > 0:
                cost = engine.costs.estimate(engine.config.risk.max_spread, quantity).total
                if signal.action == Action.LONG:
                    hit_stop = float(nxt["low"]) <= signal.stop
                    hit_target = float(nxt["high"]) >= signal.target
                    if hit_stop:
                        pnl = (signal.stop - signal.entry) * quantity - cost
                        outcome = "stop"
                    elif hit_target:
                        pnl = (signal.target - signal.entry) * quantity - cost
                        outcome = "target"
                else:
                    hit_stop = float(nxt["high"]) >= signal.stop
                    hit_target = float(nxt["low"]) <= signal.target
                    if hit_stop:
                        pnl = (signal.entry - signal.stop) * quantity - cost
                        outcome = "stop"
                    elif hit_target:
                        pnl = (signal.entry - signal.target) * quantity - cost
                        outcome = "target"
                if outcome == "no_trade":
                    exit_px = float(nxt["close"])
                    pnl = ((exit_px - signal.entry) if signal.action == Action.LONG else (signal.entry - exit_px)) * quantity - cost
                    outcome = "time_exit"
        equity += pnl
        rows.append({
            "timestamp": nxt.name,
            "equity": equity,
            "pnl": pnl,
            "quantity": quantity,
            "action": signal.action.value,
            "confidence": signal.confidence,
            "regime": signal.regime.value,
            "outcome": outcome,
        })
    if not rows:
        return pd.DataFrame(columns=["equity", "pnl", "quantity", "action", "confidence", "regime", "outcome"])
    return pd.DataFrame(rows).set_index("timestamp")

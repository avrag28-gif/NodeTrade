from __future__ import annotations

import pandas as pd

from .engine import NodeTradeEngine
from .types import Action


def run_backtest(
    candles: pd.DataFrame,
    engine: NodeTradeEngine | None = None,
    initial_equity: float = 100.0,
) -> pd.DataFrame:
    """Deterministic event-driven backtest with causal signals, sizing and costs.

    A signal at bar i is evaluated on bar i+1 only. If both stop and target are
    touched inside one OHLC bar, stop-first is used as the conservative policy.
    """
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
            stop_distance = abs(signal.entry - signal.stop)
            quantity = engine.risk.size(equity, stop_distance)
            costs = engine.costs.estimate(abs(float(nxt["close"]) - float(nxt["open"])))
            if signal.action == Action.LONG:
                hit_stop = float(nxt["low"]) <= signal.stop
                hit_target = float(nxt["high"]) >= signal.target
                if hit_stop:
                    pnl = (signal.stop - signal.entry) * quantity - costs.total * quantity
                    outcome = "stop"
                elif hit_target:
                    pnl = (signal.target - signal.entry) * quantity - costs.total * quantity
                    outcome = "target"
            else:
                hit_stop = float(nxt["high"]) >= signal.stop
                hit_target = float(nxt["low"]) <= signal.target
                if hit_stop:
                    pnl = (signal.entry - signal.stop) * quantity - costs.total * quantity
                    outcome = "stop"
                elif hit_target:
                    pnl = (signal.entry - signal.target) * quantity - costs.total * quantity
                    outcome = "target"
            if outcome == "no_trade":
                exit_px = float(nxt["close"])
                pnl = ((exit_px - signal.entry) if signal.action == Action.LONG else (signal.entry - exit_px)) * quantity - costs.total * quantity
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

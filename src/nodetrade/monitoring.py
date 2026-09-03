from __future__ import annotations

import math

import pandas as pd


def performance_report(results: pd.DataFrame) -> dict[str, float]:
    """Return stable, auditable backtest statistics from an equity/pnl table."""
    if results.empty:
        return {"trades": 0.0, "return": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "profit_factor": 0.0}
    pnl = pd.to_numeric(results["pnl"], errors="coerce").fillna(0.0)
    equity = pd.to_numeric(results["equity"], errors="coerce").ffill()
    peak = equity.cummax()
    dd = (equity / peak - 1.0).min()
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) else math.inf if len(wins) else 0.0
    trades = int((pnl != 0).sum())
    return {
        "trades": float(trades),
        "return": float(equity.iloc[-1] / equity.iloc[0] - 1.0) if equity.iloc[0] else 0.0,
        "max_drawdown": float(dd),
        "win_rate": float((pnl > 0).sum() / trades) if trades else 0.0,
        "profit_factor": pf,
    }


def degradation_flag(results: pd.DataFrame, window: int = 50, max_drawdown: float = 0.05) -> bool:
    """Flag recent deterioration; caller should reduce exposure or pause execution."""
    if len(results) < window:
        return False
    recent = results.tail(window)
    report = performance_report(recent)
    return report["max_drawdown"] <= -abs(max_drawdown) or (report["trades"] >= 10 and report["profit_factor"] < 0.8)

from __future__ import annotations

from dataclasses import dataclass

from .config import RiskConfig


@dataclass
class RiskState:
    equity: float
    day_start_equity: float
    open_risk: float = 0.0
    halted: bool = False


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None):
        self.cfg = config or RiskConfig()

    def check(self, state: RiskState, spread: float) -> tuple[bool, str]:
        if state.halted:
            return False, "risk_halted"
        if state.equity <= 0:
            return False, "invalid_equity"
        daily_dd = max(0.0, 1 - state.equity / state.day_start_equity)
        if daily_dd >= self.cfg.max_daily_drawdown:
            state.halted = True
            return False, "daily_drawdown_limit"
        if state.open_risk >= self.cfg.max_open_risk:
            return False, "open_risk_limit"
        if spread > self.cfg.max_spread:
            return False, "spread_limit"
        return True, "ok"

    def size(self, equity: float, entry: float, stop: float) -> float:
        distance = abs(entry - stop)
        if distance <= 0 or equity <= 0:
            return 0.0
        risk_cash = equity * self.cfg.risk_per_trade
        return min(risk_cash / distance, equity * self.cfg.max_position_fraction / entry)

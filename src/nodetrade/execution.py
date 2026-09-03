from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionConfig:
    slippage_per_unit: float = 0.05
    commission_per_unit: float = 0.0
    latency_bars: int = 0


@dataclass(frozen=True)
class TradeCosts:
    spread: float
    slippage: float
    commission: float

    @property
    def total(self) -> float:
        return self.spread + self.slippage + self.commission


class ExecutionCostModel:
    """Conservative transaction-cost model used by signal gating/backtests."""

    def __init__(self, config: ExecutionConfig | None = None):
        self.config = config or ExecutionConfig()

    def estimate(self, spread: float, quantity: float = 1.0) -> TradeCosts:
        q = max(0.0, float(quantity))
        return TradeCosts(
            spread=max(0.0, float(spread)),
            slippage=max(0.0, self.config.slippage_per_unit) * q,
            commission=max(0.0, self.config.commission_per_unit) * q,
        )

    def net_move(self, gross_move: float, spread: float, quantity: float = 1.0) -> float:
        return float(gross_move) - self.estimate(spread, quantity).total

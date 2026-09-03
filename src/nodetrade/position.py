from __future__ import annotations

from dataclasses import dataclass

from .types import Action


@dataclass
class Position:
    symbol: str
    action: Action
    quantity: float
    entry: float
    stop: float
    target: float
    remaining: float | None = None

    def __post_init__(self) -> None:
        if self.action == Action.WAIT:
            raise ValueError("position action cannot be WAIT")
        if self.quantity <= 0 or self.entry <= 0 or self.stop <= 0 or self.target <= 0:
            raise ValueError("position prices and quantity must be positive")
        if self.remaining is None:
            self.remaining = self.quantity

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop)

    def should_stop(self, high: float, low: float) -> bool:
        return high >= self.stop if self.action == Action.SHORT else low <= self.stop

    def should_target(self, high: float, low: float) -> bool:
        return low <= self.target if self.action == Action.SHORT else high >= self.target

    def partial_take(self, fraction: float = 0.5) -> float:
        if self.remaining is None or self.remaining <= 0:
            return 0.0
        qty = min(self.remaining, max(0.0, fraction) * self.quantity)
        self.remaining -= qty
        return qty

    @property
    def closed(self) -> bool:
        return (self.remaining or 0.0) <= 1e-12

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Regime(str, Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    BREAKOUT = "breakout"
    HIGH_VOL = "high_vol"
    UNKNOWN = "unknown"


class Action(str, Enum):
    LONG = "long"
    SHORT = "short"
    WAIT = "wait"


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: Any
    bid: float
    ask: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)


@dataclass
class Scenario:
    name: str
    probability: float
    expected_return: float
    target: float | None = None
    invalidation: float | None = None
    path: list[float] = field(default_factory=list)


@dataclass
class Signal:
    action: Action
    confidence: float
    regime: Regime
    entry: float | None
    stop: float | None
    target: float | None
    expected_value: float
    scenarios: list[Scenario] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "confidence": self.confidence,
            "regime": self.regime.value,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "expected_value": self.expected_value,
            "scenarios": [s.__dict__ for s in self.scenarios],
            "reasons": self.reasons,
        }

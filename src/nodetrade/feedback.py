from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ForecastFeedback:
    predictions: int = 0
    correct: int = 0
    brier_sum: float = 0.0

    def update(self, p_up: float, realized_up: bool) -> None:
        p = min(1.0, max(0.0, float(p_up)))
        y = 1.0 if realized_up else 0.0
        self.predictions += 1
        self.correct += int((p >= 0.5) == realized_up)
        self.brier_sum += (p - y) ** 2

    @property
    def accuracy(self) -> float:
        return self.correct / self.predictions if self.predictions else 0.0

    @property
    def brier_score(self) -> float:
        return self.brier_sum / self.predictions if self.predictions else 0.0

    @property
    def healthy(self) -> bool:
        return self.predictions < 20 or self.brier_score <= 0.25

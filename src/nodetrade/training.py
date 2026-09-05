from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .model import CausalDirectionModel
from .walkforward import walk_forward_predictions

REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class EvaluationResult:
    status: str
    samples: int
    metrics: dict[str, float]
    reason: str = ""


class ModelGate:
    """Conservative promotion gate: failed candidates never replace production."""
    def __init__(self, minimum_oos_accuracy: float = 0.50, minimum_samples: int = 100):
        self.minimum_oos_accuracy = minimum_oos_accuracy
        self.minimum_samples = minimum_samples

    def approve(self, result: EvaluationResult) -> bool:
        return result.status == "passed" and result.samples >= self.minimum_samples and result.metrics.get("oos_accuracy", 0.0) >= self.minimum_oos_accuracy


class ModelRegistry:
    """Filesystem registry with explicit promotion; training never promotes implicitly."""
    def __init__(self, root: str | Path = "models") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def register(self, version: str, metadata: dict[str, Any]) -> Path:
        path = self.root / f"{version}.json"
        path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def promote(self, version: str) -> Path:
        source = self.root / f"{version}.json"
        if not source.exists():
            raise FileNotFoundError(version)
        target = self.root / "production.json"
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target


def validate_dataset(frame: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if len(frame) < 200:
        raise ValueError("training dataset requires at least 200 rows")
    if frame[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("training dataset contains missing values")
    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("training dataset must be chronological")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("prices must be positive")


def evaluate_candidate(frame: pd.DataFrame, horizon: int = 5) -> EvaluationResult:
    """Chronological OOS evaluation. No synthetic data and no production mutation."""
    validate_dataset(frame)
    split = int(len(frame) * 0.7)
    train, test = frame.iloc[:split].copy(), frame.iloc[split:].copy()
    if len(test) < 100:
        return EvaluationResult("failed", len(test), {}, "insufficient out-of-sample data")
    model = CausalDirectionModel(horizon=horizon).fit(train)
    if not model.fitted:
        return EvaluationResult("failed", len(test), {}, "candidate model could not fit")
    # Evaluate each OOS row with the fitted candidate without leaking future data into features.
    correct = 0
    total = 0
    for i in range(len(test) - horizon):
        sample = test.iloc[: i + 1]
        pred = model.predict(sample)
        future_return = test.iloc[i + horizon].close / test.iloc[i].close - 1.0
        actual = "up" if future_return > model.flat_threshold else "down" if future_return < -model.flat_threshold else "flat"
        if max(pred.probabilities, key=pred.probabilities.get) == actual:
            correct += 1
        total += 1
    accuracy = correct / total if total else 0.0
    return EvaluationResult("passed" if accuracy >= 0.50 else "failed", total, {"oos_accuracy": accuracy})


def walk_forward_evaluate(frame: pd.DataFrame, train_size: int = 200, step: int = 20, horizon: int = 5) -> pd.DataFrame:
    validate_dataset(frame)
    return walk_forward_predictions(frame, train_size=train_size, step=step, horizon=horizon)


def training_status(dataset_path: str | Path) -> dict[str, Any]:
    path = Path(dataset_path)
    if not path.exists():
        return {"status": "pending", "reason": "training dataset not available"}
    return {"status": "ready", "dataset": str(path)}

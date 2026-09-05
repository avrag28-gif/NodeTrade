from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .backtest import run_backtest
from .model import CausalDirectionModel
from .walkforward import walk_forward

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
        return (
            result.status == "passed"
            and result.samples >= self.minimum_samples
            and result.metrics.get("oos_accuracy", 0.0) >= self.minimum_oos_accuracy
        )


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
    """Evaluation-only entry point. No production mutation and no synthetic data generation."""
    validate_dataset(frame)
    split = int(len(frame) * 0.7)
    if len(frame) - split < 100:
        return EvaluationResult("failed", len(frame) - split, {}, "insufficient out-of-sample data")
    train, test = frame.iloc[:split].copy(), frame.iloc[split:].copy()
    model = CausalDirectionModel(horizon=horizon)
    model.fit(train)
    pred = model.predict(test)
    actual = test["close"].shift(-horizon) / test["close"] - 1.0
    threshold = model.flat_threshold
    labels = actual.map(lambda r: "up" if r > threshold else "down" if r < -threshold else "flat")
    valid = labels.notna() & pred.labels.notna()
    accuracy = float((labels[valid].to_numpy() == pred.labels[valid].to_numpy()).mean()) if valid.any() else 0.0
    status = "passed" if accuracy >= 0.50 else "failed"
    return EvaluationResult(status, int(valid.sum()), {"oos_accuracy": accuracy}, "")


def training_status(dataset_path: str | Path) -> dict[str, Any]:
    path = Path(dataset_path)
    if not path.exists():
        return {"status": "pending", "reason": "training dataset not available"}
    return {"status": "ready", "dataset": str(path)}

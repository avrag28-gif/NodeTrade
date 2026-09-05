from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from .features import make_features


@dataclass(frozen=True)
class ModelPrediction:
    probabilities: dict[str, float]
    expected_return: float
    horizon: int


class CausalDirectionModel:
    """Supervised directional model. Features at t never use t+1 or later."""

    CLASSES = ("down", "flat", "up")

    def __init__(self, horizon: int = 5, flat_threshold: float = 0.001, random_state: int = 17):
        self.horizon = horizon
        self.flat_threshold = flat_threshold
        self.random_state = random_state
        self.model = HistGradientBoostingClassifier(
            max_iter=180, learning_rate=0.06, max_leaf_nodes=15,
            l2_regularization=1.0, random_state=random_state
        )
        self.columns: list[str] = []
        self.fitted = False
        self.base_rates = {c: 1 / 3 for c in self.CLASSES}

    def _dataset(self, candles: pd.DataFrame):
        x = make_features(candles)
        future_return = candles["close"].shift(-self.horizon) / candles["close"] - 1.0
        y = pd.Series(np.nan, index=candles.index)
        y[future_return < -self.flat_threshold] = 0
        y[future_return.abs() <= self.flat_threshold] = 1
        y[future_return > self.flat_threshold] = 2
        data = x.copy()
        data["_y"] = y
        data = data.replace([np.inf, -np.inf], np.nan).dropna()
        self.columns = [c for c in data.columns if c != "_y" and pd.api.types.is_numeric_dtype(data[c])]
        return data[self.columns], data["_y"].astype(int)

    def fit(self, candles: pd.DataFrame) -> "CausalDirectionModel":
        x, y = self._dataset(candles)
        if len(x) < 80 or y.nunique() < 2:
            self.fitted = False
            return self
        self.model.fit(x, y)
        counts = y.value_counts(normalize=True)
        self.base_rates = {c: float(counts.get(i, 0.0)) for i, c in enumerate(self.CLASSES)}
        self.fitted = True
        return self

    def predict(self, candles: pd.DataFrame) -> ModelPrediction:
        x = make_features(candles)
        row = x[self.columns].replace([np.inf, -np.inf], np.nan).tail(1)
        if not self.fitted or row.isna().any(axis=None):
            p = self.base_rates
        else:
            raw = self.model.predict_proba(row)[0]
            p = {self.CLASSES[int(k)]: float(v) for k, v in zip(self.model.classes_, raw)}
            for c in self.CLASSES:
                p.setdefault(c, 0.0)
        expected = p["up"] * self.flat_threshold * 2 - p["down"] * self.flat_threshold * 2
        return ModelPrediction(p, float(expected), self.horizon)

    def save(self, path: str | Path) -> Path:
        """Persist a fitted model artifact; this is never an approval/promotion operation."""
        if not self.fitted:
            raise ValueError("cannot save an unfitted model")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle:
            pickle.dump(self, handle, protocol=pickle.HIGHEST_PROTOCOL)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "CausalDirectionModel":
        target = Path(path)
        with target.open("rb") as handle:
            model = pickle.load(handle)
        if not isinstance(model, cls) or not model.fitted:
            raise ValueError("invalid or unfitted NodeTrade model artifact")
        return model

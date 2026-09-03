from __future__ import annotations

import pandas as pd

from .model import CausalDirectionModel


def walk_forward_predictions(
    candles: pd.DataFrame,
    train_size: int = 200,
    step: int = 20,
    horizon: int = 5,
) -> pd.DataFrame:
    """Generate strictly out-of-sample probabilities using expanding-window training."""
    if len(candles) <= train_size:
        return pd.DataFrame(columns=["p_down", "p_flat", "p_up", "expected_return"])
    rows = []
    for end in range(train_size, len(candles), max(1, step)):
        model = CausalDirectionModel(horizon=horizon).fit(candles.iloc[:end])
        pred = model.predict(candles.iloc[: end + 1])
        rows.append({
            "timestamp": candles.index[min(end, len(candles) - 1)],
            "p_down": pred.probabilities["down"],
            "p_flat": pred.probabilities["flat"],
            "p_up": pred.probabilities["up"],
            "expected_return": pred.expected_return,
        })
    return pd.DataFrame(rows).set_index("timestamp")

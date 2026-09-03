import numpy as np
import pandas as pd
import pytest

from nodetrade.data import validate_candles
from nodetrade.execution import ExecutionCostModel
from nodetrade.model import CausalDirectionModel


def candles(n=260):
    rng = np.random.default_rng(11)
    r = rng.normal(0.0001, 0.002, n)
    close = 2000 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    hi_base = np.maximum(open_, close)
    lo_base = np.minimum(open_, close)
    return pd.DataFrame({
        "open": open_,
        "high": hi_base * (1 + rng.uniform(0, .0015, n)),
        "low": lo_base * (1 - rng.uniform(0, .0015, n)),
        "close": close,
        "volume": rng.integers(100, 1000, n),
    })


def test_model_is_causal_and_returns_probabilities():
    df = candles()
    model = CausalDirectionModel(horizon=5).fit(df)
    prediction = model.predict(df)
    assert set(prediction.probabilities) == {"down", "flat", "up"}
    assert abs(sum(prediction.probabilities.values()) - 1) < 1e-6


def test_invalid_market_data_is_rejected():
    df = candles()
    df.loc[10, "high"] = df.loc[10, "close"] - 1
    with pytest.raises(ValueError):
        validate_candles(df)


def test_execution_costs_are_non_negative():
    costs = ExecutionCostModel().estimate(0.4, 2)
    assert costs.total >= costs.spread
    assert ExecutionCostModel().net_move(1.0, 0.2) < 1.0

import numpy as np
import pandas as pd

from nodetrade import NodeTradeEngine
from nodetrade.types import Action


def candles(n=220):
    rng = np.random.default_rng(3)
    r = rng.normal(0.0002, 0.003, n)
    close = 2000 * np.exp(np.cumsum(r))
    high = close * (1 + rng.uniform(0, .002, n))
    low = close * (1 - rng.uniform(0, .002, n))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": rng.integers(100, 1000, n)})


def test_engine_returns_valid_signal():
    signal = NodeTradeEngine().analyze(candles())
    assert signal.action in (Action.LONG, Action.SHORT, Action.WAIT)
    assert 0 <= signal.confidence <= 1


def test_insufficient_history_waits():
    signal = NodeTradeEngine().analyze(candles(20))
    assert signal.action == Action.WAIT

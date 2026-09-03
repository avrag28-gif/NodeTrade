from __future__ import annotations

import numpy as np
import pandas as pd


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create strictly causal features from OHLCV data.

    Required columns: open, high, low, close. Volume is optional.
    All rolling values use only current/past observations.
    """
    x = df.copy()
    close = x["close"].astype(float)
    ret = close.pct_change()
    x["ret_1"] = ret
    for n in (3, 5, 10, 20, 50):
        x[f"ret_{n}"] = close.pct_change(n)
        x[f"vol_{n}"] = ret.rolling(n).std()
        x[f"ma_dist_{n}"] = close / close.rolling(n).mean() - 1.0
    x["range"] = (x["high"] - x["low"]) / close.replace(0, np.nan)
    x["body"] = (x["close"] - x["open"]) / close.replace(0, np.nan)
    x["upper_wick"] = (x["high"] - x[["open", "close"]].max(axis=1)) / close.replace(0, np.nan)
    x["lower_wick"] = (x[["open", "close"]].min(axis=1) - x["low"]) / close.replace(0, np.nan)
    x["breakout_20"] = close / x["high"].rolling(20).max().shift(1) - 1.0
    x["breakdown_20"] = close / x["low"].rolling(20).min().shift(1) - 1.0
    return x.replace([np.inf, -np.inf], np.nan)

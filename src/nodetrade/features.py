from __future__ import annotations

import numpy as np
import pandas as pd


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Causal OHLCV feature engine. All features use current/past observations only."""
    x = df.copy()
    close = x["close"].astype(float)
    high = x["high"].astype(float)
    low = x["low"].astype(float)
    open_ = x["open"].astype(float)
    volume = x["volume"].astype(float) if "volume" in x else pd.Series(0.0, index=x.index)
    ret = close.pct_change()

    x["ret_1"] = ret
    for n in (3, 5, 10, 20, 50):
        x[f"ret_{n}"] = close.pct_change(n)
        x[f"vol_{n}"] = ret.rolling(n).std()
        x[f"ma_dist_{n}"] = close / close.rolling(n).mean() - 1.0

    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    x["true_range"] = tr
    x["atr_14"] = tr.rolling(14).mean()
    x["range"] = (high - low) / close.replace(0, np.nan)
    x["body"] = (close - open_) / close.replace(0, np.nan)
    x["upper_wick"] = (high - pd.concat([open_, close], axis=1).max(axis=1)) / close.replace(0, np.nan)
    x["lower_wick"] = (pd.concat([open_, close], axis=1).min(axis=1) - low) / close.replace(0, np.nan)

    ema12, ema26 = _ema(close, 12), _ema(close, 26)
    x["ema_12"] = ema12
    x["ema_26"] = ema26
    x["ema_dist_12"] = close / ema12 - 1.0
    x["ema_dist_26"] = close / ema26 - 1.0
    x["sma_20"] = close.rolling(20).mean()
    x["sma_50"] = close.rolling(50).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    x["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

    macd = ema12 - ema26
    x["macd"] = macd
    x["macd_signal"] = _ema(macd, 9)
    x["macd_hist"] = macd - x["macd_signal"]

    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    x["bb_mid"] = mid
    x["bb_upper"] = mid + 2.0 * std
    x["bb_lower"] = mid - 2.0 * std
    x["bb_width"] = (x["bb_upper"] - x["bb_lower"]) / mid.replace(0, np.nan)

    low14, high14 = low.rolling(14).min(), high.rolling(14).max()
    x["stoch_k"] = 100.0 * (close - low14) / (high14 - low14).replace(0, np.nan)
    x["stoch_d"] = x["stoch_k"].rolling(3).mean()
    tp = (high + low + close) / 3.0
    x["cci_20"] = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).apply(lambda s: np.mean(np.abs(s - np.mean(s))), raw=True)).replace(0, np.nan)
    x["momentum_10"] = close - close.shift(10)
    x["volume_z20"] = (volume - volume.rolling(20).mean()) / volume.rolling(20).std().replace(0, np.nan)
    x["vwap_20"] = (tp * volume).rolling(20).sum() / volume.rolling(20).sum().replace(0, np.nan)

    x["breakout_20"] = close / high.rolling(20).max().shift(1) - 1.0
    x["breakdown_20"] = close / low.rolling(20).min().shift(1) - 1.0
    x["swing_high_20"] = high.rolling(20).max()
    x["swing_low_20"] = low.rolling(20).min()
    x["trend_strength"] = (ema12 - ema26) / x["atr_14"].replace(0, np.nan)
    return x.replace([np.inf, -np.inf], np.nan)

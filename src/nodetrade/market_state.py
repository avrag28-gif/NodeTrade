from __future__ import annotations

import numpy as np
import pandas as pd

from .types import Regime


def detect_regime(df: pd.DataFrame) -> Regime:
    if len(df) < 60:
        return Regime.UNKNOWN
    close = df["close"].astype(float)
    ret = close.pct_change()
    vol = ret.rolling(20).std().iloc[-1]
    baseline = ret.rolling(100).std().iloc[-1]
    fast = close.rolling(10).mean().iloc[-1]
    slow = close.rolling(40).mean().iloc[-1]
    prior_high = df["high"].rolling(20).max().shift(1).iloc[-1]
    prior_low = df["low"].rolling(20).min().shift(1).iloc[-1]
    last = close.iloc[-1]
    if not all(np.isfinite(v) for v in (vol, baseline, fast, slow, prior_high, prior_low, last)):
        return Regime.UNKNOWN
    if last > prior_high or last < prior_low:
        return Regime.BREAKOUT
    if baseline > 0 and vol > baseline * 1.8:
        return Regime.HIGH_VOL
    if fast > slow * 1.001:
        return Regime.TREND_UP
    if fast < slow * 0.999:
        return Regime.TREND_DOWN
    return Regime.RANGE

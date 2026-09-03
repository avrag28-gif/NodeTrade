from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def validate_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize OHLCV without silently repairing bad market data."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    out = df.loc[:, REQUIRED_COLUMNS].copy()
    for c in REQUIRED_COLUMNS:
        out[c] = pd.to_numeric(out[c], errors="raise")
    if not out.index.is_monotonic_increasing:
        out = out.sort_index()
    if out.index.has_duplicates:
        raise ValueError("duplicate timestamps are not allowed")
    if out.isna().any().any():
        raise ValueError("OHLCV contains missing values")
    if (out[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("prices must be positive")
    if (out["high"] < out[["open", "close"]].max(axis=1)).any():
        raise ValueError("high is below open/close")
    if (out["low"] > out[["open", "close"]].min(axis=1)).any():
        raise ValueError("low is above open/close")
    if (out["volume"] < 0).any():
        raise ValueError("volume cannot be negative")
    return out


def load_csv(path: str, **kwargs) -> pd.DataFrame:
    """Load an OHLCV CSV and apply strict validation."""
    return validate_candles(pd.read_csv(path, **kwargs))

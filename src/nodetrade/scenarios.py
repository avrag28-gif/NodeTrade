from __future__ import annotations

import numpy as np
import pandas as pd

from .types import Regime, Scenario


class ScenarioEngine:
    """Generate reproducible probabilistic forward paths from causal return statistics."""

    def __init__(self, seed: int = 7, simulations: int = 400):
        self.seed = seed
        self.simulations = simulations

    def generate(self, df: pd.DataFrame, regime: Regime, horizon: int = 10) -> list[Scenario]:
        close = df["close"].astype(float).to_numpy()
        returns = np.diff(np.log(close))
        if len(returns) < 30 or horizon <= 0:
            return []
        recent = returns[-30:]
        drift = float(np.mean(recent))
        sigma = float(np.std(recent, ddof=1))
        if not np.isfinite(sigma) or sigma <= 0:
            return []
        # Seed by observable input length so identical inputs reproduce identical paths.
        rng = np.random.default_rng(self.seed + len(df) * 1009 + horizon * 9176)
        paths = np.empty((self.simulations, horizon + 1))
        paths[:, 0] = close[-1]
        shocks = rng.normal(drift, sigma, size=(self.simulations, horizon))
        paths[:, 1:] = close[-1] * np.exp(np.cumsum(shocks, axis=1))
        terminal = paths[:, -1]
        current = close[-1]
        down = terminal < current * 0.998
        flat = (terminal >= current * 0.998) & (terminal <= current * 1.002)
        up = terminal > current * 1.002
        scenarios: list[Scenario] = []
        for name, mask in (("down", down), ("flat", flat), ("up", up)):
            if not mask.any():
                continue
            subset = paths[mask]
            end = float(np.median(subset[:, -1]))
            scenarios.append(Scenario(name=name, probability=float(mask.mean()), expected_return=end / current - 1, target=end, path=[float(v) for v in np.median(subset, axis=0)]))
        return scenarios

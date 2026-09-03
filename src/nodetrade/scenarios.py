from __future__ import annotations

import numpy as np
import pandas as pd

from .types import Regime, Scenario


class ScenarioEngine:
    """Generate probabilistic forward paths from causal return statistics."""

    def __init__(self, seed: int = 7, simulations: int = 400):
        self.rng = np.random.default_rng(seed)
        self.simulations = simulations

    def generate(self, df: pd.DataFrame, regime: Regime, horizon: int = 10) -> list[Scenario]:
        close = df["close"].astype(float).to_numpy()
        returns = np.diff(np.log(close))
        if len(returns) < 30:
            return []
        recent = returns[-30:]
        drift = float(np.mean(recent))
        sigma = float(np.std(recent, ddof=1))
        if not np.isfinite(sigma) or sigma <= 0:
            return []
        paths = np.empty((self.simulations, horizon + 1))
        paths[:, 0] = close[-1]
        shocks = self.rng.normal(drift, sigma, size=(self.simulations, horizon))
        paths[:, 1:] = close[-1] * np.exp(np.cumsum(shocks, axis=1))
        terminal = paths[:, -1]
        current = close[-1]
        labels = [("down", terminal < current), ("flat", (terminal >= current * .998) & (terminal <= current * 1.002)), ("up", terminal > current)]
        scenarios: list[Scenario] = []
        for name, mask in labels:
            if not mask.any():
                continue
            p = float(mask.mean())
            subset = paths[mask]
            end = float(np.median(subset[:, -1]))
            scenarios.append(Scenario(name=name, probability=p, expected_return=end / current - 1, target=end, path=[float(x) for x in np.median(subset, axis=0)]))
        return scenarios

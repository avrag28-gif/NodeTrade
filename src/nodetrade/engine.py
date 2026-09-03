from __future__ import annotations

import pandas as pd

from .config import EngineConfig
from .execution import ExecutionCostModel
from .features import make_features
from .market_state import detect_regime
from .model import CausalDirectionModel
from .opportunity import choose_opportunity
from .risk import RiskEngine, RiskState
from .scenarios import ScenarioEngine
from .types import Action, Regime, Scenario, Signal


class NodeTradeEngine:
    """Adaptive causal decision engine: predict -> observe -> update -> execute -> recalculate."""

    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        self.scenarios = ScenarioEngine()
        self.risk = RiskEngine(self.config.risk)
        self.costs = ExecutionCostModel(self.config.execution)
        self.model = CausalDirectionModel(
            horizon=max(self.config.model.horizons),
            flat_threshold=self.config.model.flat_threshold,
        )
        self._last_fit_len = 0

    def _update_model(self, candles: pd.DataFrame) -> None:
        refresh = max(1, self.config.model.refresh_bars)
        if not self.model.fitted or len(candles) - self._last_fit_len >= refresh:
            self.model.fit(candles)
            self._last_fit_len = len(candles)

    def _fuse(self, scenarios: list[Scenario], model_probs: dict[str, float]) -> list[Scenario]:
        sim = {s.name: s.probability for s in scenarios}
        names = ("down", "flat", "up")
        fused = {n: 0.6 * model_probs.get(n, 0.0) + 0.4 * sim.get(n, 0.0) for n in names}
        total = sum(fused.values())
        if total <= 0:
            return scenarios
        fused = {n: p / total for n, p in fused.items()}
        return [Scenario(s.name, fused.get(s.name, 0.0), s.expected_return, s.target, s.invalidation, s.path) for s in scenarios]

    def analyze(
        self,
        candles: pd.DataFrame,
        bid: float | None = None,
        ask: float | None = None,
        equity: float = 100.0,
        day_start_equity: float | None = None,
    ) -> Signal:
        if len(candles) < self.config.model.min_history:
            return Signal(Action.WAIT, 0.0, Regime.UNKNOWN, None, None, None, 0.0, reasons=["insufficient_history"])
        x = make_features(candles).dropna()
        if len(x) < self.config.model.min_history:
            return Signal(Action.WAIT, 0.0, Regime.UNKNOWN, None, None, None, 0.0, reasons=["insufficient_clean_history"])

        last_close = float(x.close.iloc[-1])
        bid = last_close if bid is None else float(bid)
        ask = last_close if ask is None else float(ask)
        spread = max(0.0, ask - bid)
        state = RiskState(equity=equity, day_start_equity=day_start_equity or equity)
        ok, reason = self.risk.check(state, spread)
        regime = detect_regime(x)
        if not ok:
            return Signal(Action.WAIT, 0.0, regime, None, None, None, 0.0, reasons=[reason])

        self._update_model(candles)
        scenarios = self.scenarios.generate(x, regime, horizon=self.config.model.horizons[-1])
        prediction = self.model.predict(candles)
        scenarios = self._fuse(scenarios, prediction.probabilities)
        action, confidence, stop, target, edge, reasons = choose_opportunity(
            (bid + ask) / 2,
            spread,
            regime,
            scenarios,
            self.config.model.min_confidence,
            self.config.risk.min_reward_risk,
            self.config.execution.slippage_per_unit,
        )
        reasons = [
            f"model_p_up={prediction.probabilities.get('up', 0):.3f}",
            f"model_p_down={prediction.probabilities.get('down', 0):.3f}",
        ] + reasons
        return Signal(action, confidence, regime, (bid + ask) / 2 if action != Action.WAIT else None, stop, target, edge, scenarios, reasons)

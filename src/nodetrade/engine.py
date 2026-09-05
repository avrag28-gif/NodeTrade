from __future__ import annotations

from pathlib import Path

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
    """Production decision engine: approved model -> forecast -> risk -> decision.

    Live inference never trains or promotes a model. Training is an offline workflow.
    """

    def __init__(self, config: EngineConfig | None = None, model_registry: str | Path = "models"):
        self.config = config or EngineConfig()
        self.scenarios = ScenarioEngine()
        self.risk = RiskEngine(self.config.risk)
        self.costs = ExecutionCostModel(self.config.execution)
        self.model_registry = Path(model_registry)
        self.model: CausalDirectionModel | None = self._load_production_model()

    def _load_production_model(self) -> CausalDirectionModel | None:
        metadata_path = self.model_registry / "production.json"
        if not metadata_path.exists():
            return None
        try:
            import json
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            artifact = metadata.get("artifact")
            if not artifact:
                return None
            artifact_path = Path(artifact)
            if not artifact_path.is_absolute():
                artifact_path = self.model_registry / artifact_path.name
            return CausalDirectionModel.load(artifact_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

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

        # Fail closed until an explicitly approved production artifact is installed.
        if self.model is None:
            return Signal(Action.WAIT, 0.0, regime, None, None, None, 0.0, reasons=["production_model_unavailable"])

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

from __future__ import annotations

import pandas as pd

from .config import EngineConfig
from .features import make_features
from .market_state import detect_regime
from .opportunity import choose_opportunity
from .risk import RiskEngine, RiskState
from .scenarios import ScenarioEngine
from .types import Action, Signal


class NodeTradeEngine:
    """Causal decision loop: predict -> observe -> update -> execute -> recalculate."""

    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        self.scenarios = ScenarioEngine()
        self.risk = RiskEngine(self.config.risk)

    def analyze(self, candles: pd.DataFrame, bid: float | None = None, ask: float | None = None, equity: float = 100.0, day_start_equity: float | None = None) -> Signal:
        if len(candles) < self.config.model.min_history:
            return Signal(Action.WAIT, 0.0, __import__('nodetrade.types', fromlist=['Regime']).Regime.UNKNOWN, None, None, None, 0.0, reasons=["insufficient_history"])
        x = make_features(candles).dropna()
        if len(x) < self.config.model.min_history:
            return Signal(Action.WAIT, 0.0, __import__('nodetrade.types', fromlist=['Regime']).Regime.UNKNOWN, None, None, None, 0.0, reasons=["insufficient_clean_history"])
        last_close = float(x.close.iloc[-1])
        bid = last_close if bid is None else bid
        ask = last_close if ask is None else ask
        spread = max(0.0, ask - bid)
        state = RiskState(equity=equity, day_start_equity=day_start_equity or equity)
        ok, reason = self.risk.check(state, spread)
        regime = detect_regime(x)
        if not ok:
            return Signal(Action.WAIT, 0.0, regime, None, None, None, 0.0, reasons=[reason])
        scenarios = self.scenarios.generate(x, regime, horizon=self.config.model.horizons[-1])
        action, confidence, stop, target, edge, reasons = choose_opportunity((bid + ask) / 2, spread, regime, scenarios, self.config.model.min_confidence, self.config.risk.min_reward_risk)
        return Signal(action, confidence, regime, (bid + ask) / 2 if action != Action.WAIT else None, stop, target, edge, scenarios, reasons)

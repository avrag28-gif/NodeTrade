from __future__ import annotations

from .types import Action, Regime, Scenario


def choose_opportunity(price: float, spread: float, regime: Regime, scenarios: list[Scenario], min_confidence: float = .55, min_rr: float = 1.5):
    if not scenarios or spread <= 0:
        return Action.WAIT, 0.0, None, None, 0.0, ["insufficient_scenarios"]
    up = next((s for s in scenarios if s.name == "up"), None)
    down = next((s for s in scenarios if s.name == "down"), None)
    if not up or not down:
        return Action.WAIT, 0.0, None, None, 0.0, ["missing_directional_scenarios"]
    edge = up.probability - down.probability
    confidence = max(up.probability, down.probability)
    if confidence < min_confidence:
        return Action.WAIT, confidence, None, None, edge, ["confidence_below_gate"]
    if edge > 0:
        target = up.target
        stop = price - max(abs(price - (down.target or price)), spread * 2)
        rr = abs(target - price) / max(abs(price - stop), 1e-9) if target else 0
        if rr >= min_rr and regime not in (Regime.TREND_DOWN,):
            return Action.LONG, confidence, stop, target, edge, ["upside_probability_dominates", f"rr={rr:.2f}"]
    if edge < 0:
        target = down.target
        stop = price + max(abs((up.target or price) - price), spread * 2)
        rr = abs(target - price) / max(abs(stop - price), 1e-9) if target else 0
        if rr >= min_rr and regime not in (Regime.TREND_UP,):
            return Action.SHORT, confidence, stop, target, edge, ["downside_probability_dominates", f"rr={rr:.2f}"]
    return Action.WAIT, confidence, None, None, edge, ["risk_reward_or_regime_gate"]

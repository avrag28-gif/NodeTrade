from __future__ import annotations

from .types import Action, Regime, Scenario


def choose_opportunity(
    price: float,
    spread: float,
    regime: Regime,
    scenarios: list[Scenario],
    min_confidence: float = .55,
    min_rr: float = 1.5,
    extra_cost: float = 0.05,
):
    if not scenarios or spread < 0:
        return Action.WAIT, 0.0, None, None, 0.0, ["insufficient_scenarios"]
    up = next((s for s in scenarios if s.name == "up"), None)
    down = next((s for s in scenarios if s.name == "down"), None)
    if not up or not down:
        return Action.WAIT, 0.0, None, None, 0.0, ["missing_directional_scenarios"]

    edge = up.probability - down.probability
    confidence = max(up.probability, down.probability)
    if confidence < min_confidence:
        return Action.WAIT, confidence, None, None, edge, ["confidence_below_gate"]

    cost = max(0.0, spread) + max(0.0, extra_cost)
    if edge > 0 and regime != Regime.TREND_DOWN:
        target = up.target
        stop = price - max(abs(price - (down.target or price)), spread * 2)
        reward = abs(target - price) if target else 0.0
        risk = abs(price - stop)
        rr = reward / max(risk, 1e-9)
        ev = up.probability * reward - (1 - up.probability) * risk - cost
        if rr >= min_rr and ev > 0:
            return Action.LONG, confidence, stop, target, ev, ["upside_probability_dominates", f"rr={rr:.2f}", f"net_ev={ev:.5f}"]

    if edge < 0 and regime != Regime.TREND_UP:
        target = down.target
        stop = price + max(abs((up.target or price) - price), spread * 2)
        reward = abs(target - price) if target else 0.0
        risk = abs(stop - price)
        rr = reward / max(risk, 1e-9)
        ev = down.probability * reward - (1 - down.probability) * risk - cost
        if rr >= min_rr and ev > 0:
            return Action.SHORT, confidence, stop, target, -ev, ["downside_probability_dominates", f"rr={rr:.2f}", f"net_ev={ev:.5f}"]

    return Action.WAIT, confidence, None, None, edge, ["risk_reward_or_ev_or_regime_gate"]

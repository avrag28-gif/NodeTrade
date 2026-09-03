from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LossCause(str, Enum):
    PREDICTION = "prediction_error"
    ENTRY = "late_or_bad_entry"
    STOP = "stop_too_tight"
    REGIME = "regime_change"
    EXECUTION = "execution_cost_or_slippage"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RecoveryDecision:
    cause: LossCause
    risk_multiplier: float
    pause_bars: int
    action: str


class LossRecoveryEngine:
    """Diagnose losses and de-risk; never increases size to recover losses."""

    def diagnose(
        self,
        predicted_direction_correct: bool,
        entry_was_validated: bool,
        stop_distance: float,
        adverse_excursion: float,
        regime_changed: bool,
        slippage: float,
        expected_slippage: float,
    ) -> RecoveryDecision:
        if slippage > max(expected_slippage * 2, 0.0):
            return RecoveryDecision(LossCause.EXECUTION, 0.5, 2, "reduce_exposure")
        if regime_changed:
            return RecoveryDecision(LossCause.REGIME, 0.25, 5, "pause_and_refit")
        if stop_distance > 0 and adverse_excursion < stop_distance * 0.25:
            return RecoveryDecision(LossCause.STOP, 0.5, 1, "widen_only_if_new_structure_confirms")
        if not entry_was_validated:
            return RecoveryDecision(LossCause.ENTRY, 0.5, 1, "tighten_entry_gate")
        if not predicted_direction_correct:
            return RecoveryDecision(LossCause.PREDICTION, 0.5, 2, "reduce_exposure_and_refresh_model")
        return RecoveryDecision(LossCause.UNKNOWN, 0.5, 1, "reduce_exposure")

from nodetrade.recovery import LossCause, LossRecoveryEngine


def test_recovery_never_martingales():
    decision = LossRecoveryEngine().diagnose(False, True, 2.0, 2.0, False, 0.1, 0.01)
    assert decision.cause == LossCause.EXECUTION
    assert decision.risk_multiplier <= 1.0


def test_regime_change_pauses_and_refits():
    decision = LossRecoveryEngine().diagnose(False, True, 2.0, 2.0, True, 0.01, 0.01)
    assert decision.pause_bars > 0
    assert decision.action == "pause_and_refit"

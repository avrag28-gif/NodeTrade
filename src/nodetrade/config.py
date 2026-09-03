from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: float = 0.005
    max_daily_drawdown: float = 0.02
    max_open_risk: float = 0.01
    max_spread: float = 2.5
    min_reward_risk: float = 1.5
    max_position_fraction: float = 0.25


@dataclass(frozen=True)
class ModelConfig:
    lookback: int = 64
    horizons: tuple[int, ...] = (1, 3, 5, 10, 20)
    min_history: int = 100
    min_confidence: float = 0.55


@dataclass(frozen=True)
class EngineConfig:
    risk: RiskConfig = RiskConfig()
    model: ModelConfig = ModelConfig()

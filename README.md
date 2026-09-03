# NodeTrade

Adaptive, scenario-based XAUUSD research and trading engine.

## Implemented now
- Causal OHLCV feature pipeline
- Market regime detection
- Probabilistic forward-path simulation
- Opportunity gate with confidence, spread and reward/risk filters
- Equity-based risk limits and position sizing
- Event-driven research backtest baseline
- Pytest smoke tests
- GitHub Actions CI

## Architecture
1. Market State Engine
2. Forward Scenario Engine
3. Adaptive Opportunity Engine
4. Execution & Cost Engine (interface to be connected to a broker)
5. Risk & Capital Engine
6. Position Management
7. Feedback / Model Monitoring

Core loop: **predict → observe → update → execute → recalculate**.

## Design rules
- No look-ahead features.
- No martingale loss recovery.
- Spread is treated as a trading cost and can block entries.
- Risk limits are independent from model confidence.
- WAIT is a valid outcome when evidence is weak.
- Backtests must be treated as research, not proof of future profitability.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
pytest -q
```

## Data contract

Backtest/analysis input is a pandas DataFrame with `open`, `high`, `low`, `close`; `volume` is optional. Timestamps should be the DataFrame index and data must be sorted chronologically.

## Safety

This repository does not guarantee profits, zero losses, or a fixed return. Live trading requires a separately configured broker/execution adapter, validated market data, and paper/OOS testing before risking capital.

# NodeTrade

Adaptive AI-assisted XAUUSD trading engine built around causal features, supervised directional prediction, forward scenarios, execution costs, risk controls, and walk-forward evaluation.

## Implemented

- Strict OHLCV validation and CSV ingestion
- Causal feature engineering with no future inputs
- Market-regime detection
- Reproducible probabilistic forward-path simulation
- Supervised 3-state directional ML model: down / flat / up
- Periodic model refresh while new candles arrive
- Model + scenario probability fusion
- Cost-aware opportunity selection using reward/risk and net-EV gates
- Equity-based position sizing and daily/open-risk limits
- Deterministic event-driven backtesting with conservative stop-first OHLC handling
- Walk-forward out-of-sample prediction utility
- Performance report and model-degradation flag
- Broker adapter protocol
- Deterministic paper broker for integration testing
- Pytest test suite
- GitHub Actions CI

## Architecture

1. **Market State Engine** — trend, range, breakout and volatility state.
2. **Feature Engine** — strictly causal OHLCV transformations.
3. **AI Direction Model** — supervised probabilities for future down/flat/up movement.
4. **Forward Scenario Engine** — probabilistic future price paths.
5. **Opportunity Engine** — combines model/scenario evidence and rejects trades whose expected value does not clear estimated costs.
6. **Risk & Capital Engine** — equity-based sizing, spread gate, daily drawdown and open-risk limits.
7. **Execution Cost Engine** — spread, slippage and commission abstraction.
8. **Broker Interface** — common order/fill contract plus paper implementation.
9. **Monitoring** — return, drawdown, win rate, profit factor and degradation detection.
10. **Walk-Forward Evaluation** — chronological training/prediction without look-ahead.

Core loop: **predict → observe → update → execute → recalculate**.

## Adaptive entry logic

NodeTrade does not require one fixed entry path. The opportunity layer can wait for evidence rather than forcing a trade. The architecture supports extending the same gate to pullback, momentum, breakout/retest and reversal states without changing the risk layer.

## Risk rules

- No martingale recovery.
- No unlimited compounding assumptions.
- Spread/costs are part of the decision.
- Position size is determined from equity and invalidation distance, not confidence alone.
- Daily drawdown and open-risk limits can halt new entries.
- `WAIT` is a first-class decision.
- The system does not promise profit or zero losses.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
pytest -q
```

## Data contract

Analysis/backtest input is a pandas DataFrame containing `open`, `high`, `low`, `close`, and `volume`. Timestamps should be the DataFrame index and data must be chronological with no duplicate timestamps. `nodetrade.data.validate_candles()` rejects malformed market data instead of silently repairing it.

## Live deployment boundary

The broker interface and paper broker are implemented. A real-money deployment still requires a broker-specific adapter, authenticated credentials supplied outside source control, live market-data transport, and operational controls such as connectivity/reconnect handling. Those pieces are intentionally adapter-specific and must not be faked with hard-coded credentials.

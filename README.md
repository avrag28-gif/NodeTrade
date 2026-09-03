# NodeTrade

Adaptive AI-assisted XAUUSD trading engine built around causal features, supervised directional prediction, forward scenarios, execution costs, risk controls, and walk-forward evaluation.

> **Purpose:** this repository contains the trading decision engine. MetaTrader 5 (MT5) is the planned execution terminal. The intended deployment is a VPS where MT5 is installed and an AI/desktop agent can operate the terminal and connect it to NodeTrade. No broker password, API key, or terminal credential belongs in this repository.

## 1. What NodeTrade does

NodeTrade is a decision system, not a single-indicator strategy. At each decision point it follows:

**market data → causal features → market state → ML direction probability → forward scenarios → probability fusion → cost/EV gate → risk sizing → signal → execution → observation → feedback**

The system can return `WAIT`. It is deliberately not forced to trade continuously.

The model is designed to answer these questions:

1. What direction has the highest conditional probability?
2. Is the current price already a valid entry or is waiting better?
3. What forward paths are plausible?
4. Where is the invalidation level?
5. Does the expected move remain positive after spread/slippage/commission assumptions?
6. How large may the position be under current equity and risk limits?
7. After a trade, was the forecast wrong, the entry late, the stop too tight, or the market regime different?

It does **not** claim deterministic future prices, zero losses, or guaranteed profitability.

## 2. Repository architecture

```text
src/nodetrade/
├── cli.py                  # command-line entry points
├── config.py               # risk/model/engine configuration
├── data.py                 # candle validation and CSV ingestion
├── types.py                # market/signal/scenario contracts
├── features.py             # strictly causal features
├── market_state.py         # regime/state detection
├── model.py                # supervised down/flat/up model
├── scenarios.py             # reproducible forward-path simulation
├── opportunity.py          # model + scenario + cost-aware trade gate
├── risk.py                 # sizing and account-level risk limits
├── execution.py            # execution-cost abstraction
├── execution_engine.py     # order lifecycle / execution orchestration
├── broker.py               # broker protocol and paper broker
├── position.py             # position lifecycle and partial exits
├── feedback.py             # post-trade diagnosis / recovery logic
├── monitoring.py           # performance and degradation monitoring
├── walkforward.py          # chronological OOS evaluation
├── backtest.py             # event-driven research backtest
└── engine.py               # top-level decision orchestration
```

### Important separation

- **NodeTrade** decides *what should be done*.
- **MT5** is the terminal/execution environment.
- The **VPS desktop agent** is responsible for installing/configuring the environment and operating MT5 according to the adapter/runbook.
- Credentials remain local to the VPS/MT5 environment.

Do not paste passwords, investor passwords, API tokens, GitHub tokens, or `.env` secrets into GitHub.

## 3. Current implementation status

### Implemented

- Strict OHLCV validation and CSV ingestion
- Causal feature engineering with no future inputs
- Market-regime detection
- Reproducible probabilistic forward-path simulation
- Supervised 3-state directional ML model: `down / flat / up`
- Periodic model refresh while new candles arrive
- Model + scenario probability fusion
- Cost-aware opportunity selection using reward/risk and net-EV gates
- Equity-based position sizing and daily/open-risk limits
- Deterministic event-driven backtesting with conservative stop-first OHLC handling
- Walk-forward out-of-sample prediction utility
- Performance report and model-degradation flag
- Broker adapter protocol
- Deterministic paper broker for integration testing
- Position lifecycle and non-martingale loss recovery logic
- CLI signal/backtest interface
- Pytest test suite
- GitHub Actions CI

### MT5 boundary

The Python core is broker-neutral. The final desktop integration should be an **MT5 adapter/bridge**, not a fake direct-broker API. The bridge must translate:

- MT5 symbol/tick/candle data → NodeTrade market snapshots/DataFrames
- NodeTrade `LONG/SHORT/WAIT` → MT5 pending/market order instructions
- NodeTrade stop/target/size → MT5 order parameters
- MT5 fills/rejections/partial fills → NodeTrade execution events
- MT5 open positions/account equity → NodeTrade risk state

## 4. MT5 integration contract for the VPS agent

The VPS agent should treat the following as the integration contract.

### 4.1 Environment

Required on the VPS:

- Windows VPS with MetaTrader 5 installed
- Python 3.10+ matching the repository requirements
- Git
- A working MT5 terminal/account connection
- A dedicated directory for NodeTrade
- Local environment variables/configuration for any credentials
- Stable internet connection and correct VPS clock/time synchronization

The agent should first clone the repository, create a virtual environment, install dependencies, and run the full test suite before enabling any live execution.

### 4.2 MT5 data mapping

Use the MT5 terminal as the source of truth for the traded symbol and account state.

Minimum candle schema supplied to NodeTrade:

```text
time, open, high, low, close, volume
```

Normalize timestamps to one consistent timezone before feature generation. Do not mix candle boundaries from different timezones or timeframes.

For XAUUSD, the exact symbol name is broker-dependent (`XAUUSD`, `XAUUSDm`, `GOLD`, etc.). The agent must discover the symbol actually exposed by the installed MT5 terminal instead of hard-coding an assumed suffix.

### 4.3 Bid/ask handling

Never manufacture a zero spread for live execution.

For every live decision:

- read current MT5 bid
- read current MT5 ask
- calculate `ask - bid`
- reject the trade when the configured spread limit is exceeded
- use the correct side of the market for entry/exit calculations

This is especially important for XAUUSD because the decision price and executable price are not necessarily identical.

### 4.4 Order mapping

NodeTrade signal:

```text
WAIT  → no order
LONG  → buy order
SHORT → sell order
```

Before sending an order the adapter must validate:

1. symbol is visible/tradable
2. market is open
3. volume is within MT5 min/max/step
4. stop distance satisfies broker stop-level rules
5. current spread is acceptable
6. account equity/risk state allows the trade
7. the signal has not become stale

After submission, verify the MT5 result. A requested order is **not** the same thing as a filled order.

Handle at minimum:

- accepted/fill
- rejected
- requote/price change
- invalid volume
- invalid stops
- market closed
- insufficient margin
- connection failure
- partial fill where supported
- duplicate-order prevention

## 5. VPS deployment sequence

The desktop agent should execute this sequence rather than improvising the architecture.

### Phase A — install

1. Install/verify Git, Python, and MT5.
2. Log into the intended MT5 account manually.
3. Confirm the intended XAUUSD symbol exists.
4. Clone `avrag28-gif/NodeTrade`.
5. Create a Python virtual environment.
6. Install the project and test dependencies.
7. Run `pytest -q`.
8. Do not enable automated live orders yet.

### Phase B — paper/integration test

1. Connect the bridge to MT5 market data.
2. Read candles and current bid/ask.
3. Validate the data schema and timestamps.
4. Run NodeTrade signal generation.
5. Send **no live orders**.
6. Compare generated signals with the MT5 chart manually.
7. Exercise order/rejection/error handling using the paper broker or a non-live test path.
8. Confirm position state is reconciled correctly after restarts.

### Phase C — controlled live activation

Only after the previous phases pass:

1. Start with the smallest broker-allowed volume.
2. Keep NodeTrade's risk limits enabled.
3. Keep a hard daily drawdown stop and open-risk cap.
4. Log every signal, decision, order request, MT5 response, fill, SL/TP change, and final result.
5. Stop automation if data becomes stale, MT5 disconnects, spread becomes abnormal, or state reconciliation fails.

## 6. Operational loop

The intended live process is:

```text
┌───────────────┐
│ MT5 tick/data │
└───────┬───────┘
        ↓
┌────────────────────┐
│ candle/snapshot    │
│ validation         │
└────────┬───────────┘
         ↓
┌────────────────────┐
│ causal features    │
└────────┬───────────┘
         ↓
┌────────────────────┐
│ regime + ML model  │
└────────┬───────────┘
         ↓
┌────────────────────┐
│ forward scenarios  │
└────────┬───────────┘
         ↓
┌────────────────────┐
│ EV / spread / RR   │
└────────┬───────────┘
         ↓
┌────────────────────┐
│ risk + position    │
│ sizing             │
└────────┬───────────┘
         ↓
     LONG/SHORT/WAIT
         ↓
┌────────────────────┐
│ MT5 execution      │
└────────┬───────────┘
         ↓
┌────────────────────┐
│ observe fill/state │
└────────┬───────────┘
         ↓
┌────────────────────┐
│ feedback/monitor   │
└────────┬───────────┘
         └──────→ recalculate
```

The system must be **state-aware**. It should not blindly resend an order on every tick. The bridge needs an idempotency/order-state layer so the same signal cannot create duplicate positions.

## 7. Adaptive entry behavior

NodeTrade is intentionally not a one-entry-only strategy.

The execution/decision layer should support these conditional paths:

- ideal pullback entry
- momentum entry
- breakout entry
- breakout/retest entry
- continuation entry
- reversal entry
- `WAIT` until evidence improves

Example:

```text
Expected path:
3500 → 3494 pullback → 3508 continuation

If 3494 is touched:
    evaluate the pullback setup.

If price instead moves:
3500 → 3508 → 3515

Do not chase automatically.
Recalculate the forward path and determine whether a momentum/continuation
entry has sufficient net EV. Otherwise WAIT.
```

This is a key design principle: **a missed ideal entry does not mean the system must enter late.** It recalculates.

## 8. Risk and loss handling

Loss recovery is diagnostic, not martingale.

After a losing trade, classify the event where possible:

- directional forecast wrong
- entry too late
- stop too tight
- regime changed
- spread/slippage abnormal
- data/latency problem
- execution failure

Then adjust according to configured policy: reduce exposure, switch/refresh model, pause, or continue normally. Never increase size merely because the previous trade lost.

Risk sizing must use actual MT5 symbol properties when the adapter is live:

- minimum/maximum volume
- volume step
- contract size
- tick size
- tick value
- margin requirement
- stop-level/freeze-level rules
- account currency

Do not assume Python's generic price-distance sizing is identical to MT5's monetary P/L calculation.

## 9. Model training and anti-leakage rules

Training labels are allowed to reference future prices because the label represents what happened after the historical decision point. **Features must never contain future information.**

For OOS evaluation:

```text
TRAIN: [past only] ───────┐
                          ↓
                       PREDICT
                          ↓
TEST:  [future unseen] ──┘
```

Never randomly shuffle time-series samples across train/test boundaries.

The VPS agent must not retrain on future candles and then evaluate those same candles as if they were unseen. Use chronological/walk-forward evaluation.

## 10. What the AI/desktop agent must NOT do

- Do not invent a broker API that does not exist.
- Do not hard-code MT5 credentials into source files.
- Do not commit credentials to GitHub.
- Do not disable risk limits to increase returns.
- Do not use martingale/grid escalation as loss recovery unless explicitly redesigned and separately risk-reviewed.
- Do not bypass spread, stop-distance, margin, or volume checks.
- Do not duplicate orders after reconnect/restart.
- Do not treat an order request as a confirmed fill.
- Do not use future candles in live features.
- Do not optimize parameters on the same data used to claim OOS performance.
- Do not claim a profitable result before a reproducible OOS/paper/live validation record exists.

## 11. Configuration and secrets

Keep deployment secrets outside Git. Recommended environment variables/configuration include only local values such as:

```text
MT5_TERMINAL_PATH
MT5_SYMBOL
MT5_TIMEFRAME
NODETRADE_MODE=paper
NODETRADE_LOG_LEVEL=INFO
```

The exact MT5 login/account secret handling should remain inside the terminal or secure VPS secret store. Never place passwords in `.py`, `.json`, `.yaml`, README, or GitHub Actions logs.

## 12. Verification checklist for the VPS agent

Before saying the system is ready, verify all of these:

- [ ] Repository cloned successfully
- [ ] Dependencies installed
- [ ] `pytest -q` passes
- [ ] MT5 launches and remains connected
- [ ] Intended account is confirmed
- [ ] Correct XAUUSD symbol is identified
- [ ] Candle timeframe is confirmed
- [ ] Timestamps are consistent
- [ ] Bid/ask are read from MT5
- [ ] Spread gate works
- [ ] NodeTrade returns `LONG/SHORT/WAIT`
- [ ] Signal is not stale before execution
- [ ] Volume is normalized to MT5 step/min/max
- [ ] SL/TP satisfy MT5 constraints
- [ ] Order result is checked
- [ ] Open positions are reconciled after restart
- [ ] Duplicate orders are prevented
- [ ] Disconnect/reconnect behavior is tested
- [ ] Daily drawdown kill switch works
- [ ] Open-risk limit works
- [ ] Logging is persistent
- [ ] Secrets are not in the repository
- [ ] Paper/integration validation completed before live activation

If any critical item fails, the correct action is **STOP**, not force execution.

## 13. Quick start for development

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -e ".[test]"
pytest -q

# CLI help
python -m nodetrade.cli --help
```

## 14. Data contract

Analysis/backtest input is a pandas DataFrame containing `open`, `high`, `low`, `close`, and `volume`. Timestamps should be the DataFrame index and data must be chronological with no duplicate timestamps. `nodetrade.data.validate_candles()` rejects malformed market data instead of silently repairing it.

## 15. Backtesting interpretation

The backtest and walk-forward modules are engineering validation tools. They are not proof of future profitability. Historical OHLC data can hide intrabar ordering, liquidity, spread, latency, and execution effects. For meaningful validation, compare results across multiple periods/regimes and include realistic costs.

## 16. Safety / reality boundary

NodeTrade is built to make trading decisions under explicit uncertainty and risk controls. It cannot guarantee profit, zero losses, a fixed return, or a particular account-growth path. High leverage can magnify losses as well as gains.

The objective of the implementation is therefore **robust, testable, reproducible execution logic**, not a fabricated certainty of future price movement.

## 17. For the VPS AI agent — first task

When this repository is given to an AI/desktop agent, the agent should:

1. Read this README completely.
2. Inspect every file under `src/nodetrade/` and `tests/` before modifying anything.
3. Run the existing test suite.
4. Understand the signal/risk/execution contracts.
5. Detect the installed MT5 terminal and actual XAUUSD symbol.
6. Build the MT5 bridge as a separate adapter layer rather than rewriting the core engine.
7. Run paper/integration tests.
8. Only then prepare controlled live execution.
9. Never expose or commit credentials.
10. Leave the core risk controls enabled.

The agent should prefer **small, auditable integration changes** over replacing the decision engine with an unrelated strategy.

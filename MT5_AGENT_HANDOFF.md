# MT5 VPS Agent Handoff

## Mission

Integrate the existing NodeTrade decision engine with the MetaTrader 5 desktop terminal on this VPS. Do not replace NodeTrade with a new strategy unless a code defect requires it.

## Read first

1. `README.md`
2. all files under `src/nodetrade/`
3. all files under `tests/`
4. `pyproject.toml`

## Architecture

```text
MT5 terminal
   │
   ├── ticks / candles / account state
   ↓
MT5 adapter / bridge
   ↓
NodeTrade Engine
   ├── causal features
   ├── regime detection
   ├── ML direction model
   ├── forward scenarios
   ├── cost-aware opportunity gate
   └── risk engine
   ↓
LONG / SHORT / WAIT
   ↓
MT5 adapter
   ↓
order result / fill / position state
   ↓
feedback + monitoring
```

## Rules

- MT5 is the execution terminal; do not invent a direct broker API.
- Keep the core NodeTrade engine broker-neutral.
- Discover the broker's actual gold symbol instead of assuming `XAUUSD`.
- Read real MT5 bid/ask; never fake spread in live mode.
- Reconcile positions after startup and reconnect.
- Make order submission idempotent to prevent duplicates.
- Validate volume against MT5 min/max/step.
- Validate SL/TP against MT5 stop/freeze constraints.
- Confirm the actual trade result; request != fill.
- Stop on stale data, lost connection, abnormal spread, failed reconciliation, or risk-limit violation.
- Never commit credentials.
- Never disable risk controls to increase returns.
- Never use martingale recovery.

## Deployment order

1. Clone repository.
2. Create virtual environment.
3. Install dependencies.
4. Run `pytest -q`.
5. Launch MT5 and confirm account.
6. Discover and select the real gold symbol.
7. Read candles/ticks and map them to NodeTrade.
8. Verify timestamps and timeframe boundaries.
9. Run signal generation with no live orders.
10. Run paper/integration tests.
11. Test reconnect/restart reconciliation.
12. Test spread, volume, margin and invalid-stop rejection paths.
13. Only after all checks pass, enable controlled live execution.

## Required live state

Persist enough state to recover safely after process restart:

- last processed candle/tick timestamp
- active signal identity
- submitted order identity
- MT5 ticket/order/deal identifiers
- current position state
- entry price and volume
- stop and target
- realized/unrealized P/L
- current equity snapshot
- risk halt state

## Signal handling

`WAIT` means do nothing.

`LONG` and `SHORT` must pass the final execution checks again immediately before sending. A signal that became stale must be discarded and recalculated.

## Adaptive paths

Do not assume the ideal pullback will happen. If the market moves directly through the forecasted area, recalculate. A continuation/momentum entry is allowed only when the fresh probability and cost/risk gates support it. Otherwise wait.

## Secrets

Keep MT5 login information inside the terminal or secure local VPS configuration. Do not put it in:

- source code
- README
- `.env` committed to Git
- JSON/YAML checked into Git
- command-line history where avoidable
- GitHub Actions output

## Completion criteria

The integration is complete only when the agent can demonstrate:

- MT5 data reaches NodeTrade correctly
- NodeTrade returns deterministic, inspectable signals for the same input state
- real bid/ask cost gating works
- risk sizing maps correctly to MT5 monetary P/L
- orders are submitted only after final checks
- fills/rejections are recorded
- open positions reconcile after restart
- duplicate orders are prevented
- disconnect handling is safe
- kill switches stop new orders
- logs provide an audit trail
- all repository tests pass

A live system should be considered **not ready** if any critical completion criterion fails.
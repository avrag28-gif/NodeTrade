# NodeTrade

Adaptive AI-assisted XAUUSD trading engine built around causal features, supervised directional prediction, forward scenarios, execution costs, risk controls, and walk-forward evaluation.

## Core concept

NodeTrade is not a conventional indicator-only EA. Its decision loop is:

`predict -> observe -> update -> execute -> recalculate`

The engine combines causal features, market-regime detection, a supervised directional model, probabilistic forward scenarios, cost-aware opportunity selection, and risk gates. The decision can be `LONG`, `SHORT`, or `WAIT`. The scenario layer supports alternative paths such as ideal pullback, momentum, breakout/retest, continuation, and reversal rather than requiring one fixed entry path.

**Do not replace this decision architecture with a simpler indicator strategy when building integrations.**

## Repository architecture

- `src/nodetrade/features.py` — strictly causal feature engineering.
- `src/nodetrade/market_state.py` — regime detection.
- `src/nodetrade/model.py` — causal 3-state directional model.
- `src/nodetrade/scenarios.py` — reproducible probabilistic forward paths.
- `src/nodetrade/opportunity.py` — LONG/SHORT/WAIT opportunity gate.
- `src/nodetrade/risk.py` — drawdown, spread, open-risk gates and sizing primitive.
- `src/nodetrade/execution.py` — execution-cost model.
- `src/nodetrade/execution_engine.py` — execution orchestration.
- `src/nodetrade/position.py` — position lifecycle and partial exits.
- `src/nodetrade/feedback.py` — post-trade diagnosis and non-martingale recovery logic.
- `src/nodetrade/backtest.py` — event-driven research backtest.
- `src/nodetrade/walkforward.py` — chronological out-of-sample evaluation.
- `src/nodetrade/monitoring.py` — performance/model degradation monitoring.
- `src/nodetrade/api.py` — optional authenticated HTTP boundary for MT5.
- `src/nodetrade/server.py` — API server entrypoint.
- `integrations/mt5/NodeTradeEA.mq5` — MT5-side bridge.
- `integrations/mt5/README.md` — MT5 integration and production checklist.
- `MT5_AGENT_HANDOFF.md` — VPS desktop-agent handoff.

## MT5 service architecture

The preferred product architecture is:

```text
MT5 terminal / broker account
        |
        | NodeTrade EA (.mq5 -> .ex5)
        | authenticated HTTPS
        v
NodeTrade API server
        |
        v
NodeTrade Core Engine
        |
        +--> prediction
        +--> regime
        +--> scenario/path analysis
        +--> opportunity gate
        +--> risk policy
        |
        v
LONG / SHORT / WAIT + levels
        |
        v
EA validates freshness/authorization and can execute in MT5
        |
        v
Trade transaction / outcome feedback
        |
        v
Monitoring + diagnosis + training dataset pipeline
```

The broker password is never required by the NodeTrade server. The EA runs inside the user's MT5 terminal, which is already connected to the broker. The server receives only the market/account/execution state required by the NodeTrade contract.

This replaces the earlier VPS-agent-only execution route as the scalable product boundary. The VPS desktop-agent route remains useful for development and deployment automation; it is not part of the AI decision architecture.

## Authentication and licensing

The API includes a small SQLite `LicenseStore` primitive. Activation keys are stored as keyed SHA-256 HMAC digests rather than plaintext and are bound to an MT5 account ID. Expiration and server-side enable/disable are supported.

The intended user experience is:

1. User registers.
2. Server provisions an account ID and activation code.
3. User downloads the signed/approved NodeTrade EA (`.ex5`).
4. User installs it in MT5.
5. User enters the NodeTrade API URL, account ID and activation code.
6. EA authenticates through HTTPS and sends market/account state.
7. Authorized requests reach the unchanged NodeTrade engine.
8. EA receives the decision and, when explicitly enabled, performs broker execution locally.

The activation code is a secret. Do not log it or commit it. Production provisioning/admin tooling is intentionally separate from the runtime API and must be secured before multi-user rollout.

## API

Install server dependencies with:

```bash
pip install -e ".[server]"
```

Run the development service:

```bash
export NODETRADE_LICENSE_SECRET="use-a-long-random-secret"
uvicorn nodetrade.server:app --host 127.0.0.1 --port 8000
```

Production must use HTTPS behind an appropriate reverse proxy, authentication/rate limiting, persistent storage, backups, monitoring, and restricted network access. Never expose a raw development server directly to the public internet.

### `POST /v1/analyze`

The EA sends:

- account ID and activation key;
- broker symbol name;
- bid/ask;
- equity;
- optional day-start equity;
- bounded OHLCV history.

The server validates the license and calls `NodeTradeEngine.analyze()`.

The current response contains the NodeTrade signal, regime, confidence, entry/stop/target, expected value, scenarios and reasons. The current bridge is deliberately conservative: the EA defaults to `InpLiveTrading=false` because production lot sizing must first incorporate the broker's actual contract specification.

## MT5 requirements before live execution

The EA uses standard MT5 facilities including `CopyRates`, `SymbolInfoTick`, account information, `WebRequest`, `CTrade`, position inspection and `OnTradeTransaction`.

Before production live trading, the bridge must additionally implement and validate:

- deterministic signal IDs/idempotency keys;
- signal timestamp and expiry/staleness checks;
- broker/symbol contract data: tick size, tick value, contract size, volume min/max/step, digits, stops level, freeze level and margin mode;
- server-side volume calculation consistent with NodeTrade risk policy;
- current positions and pending orders in the request;
- daily-start equity persistence;
- open-risk persistence/reconciliation;
- order/deal/position reconciliation after restart;
- explicit handling of netting vs hedging accounts;
- trade-server retcode validation and partial-fill handling;
- retry rules that cannot duplicate orders;
- server heartbeat/session handling;
- trade-result feedback endpoint;
- secure secrets and TLS certificate validation;
- production license provisioning/revocation tooling.

A successful `CTrade.Buy()`/`Sell()` call alone is not sufficient evidence of execution; the EA must inspect the trade-server result and subsequent transaction state.

## MT5 setup

See [`integrations/mt5/README.md`](integrations/mt5/README.md) and `MT5_AGENT_HANDOFF.md`.

In MT5, the API origin must be explicitly allowed under **Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL** before `WebRequest()` can reach it.

Start with:

```text
InpLiveTrading = false
```

Validate authentication, data quality, signal freshness, reconnection, duplicate protection and transaction reconciliation on a demo account before enabling unattended execution.

## Data and training

The EA can provide market and permitted account/trade outcome data to the NodeTrade service. Data ingestion and training must remain separated from live inference:

```text
MT5 data -> validation -> storage -> training dataset
                                      |
                                      v
                         chronological walk-forward evaluation
                                      |
                                      v
                              model evaluation
                                      |
                                      v
                               model registry
                                      |
                                      v
                              production model
```

A trade outcome must not cause an uncontrolled immediate model rewrite. Training remains subject to causal feature construction, chronological evaluation, monitoring and explicit model promotion.

## Risk and reality boundary

No strategy can guarantee profit or perfectly predict future prices. NodeTrade therefore uses risk gates, cost awareness, WAIT decisions, scenario alternatives, and non-martingale loss diagnosis. Position sizing must be based on equity and true invalidation distance plus broker contract economics, not confidence alone.

## Development

Install tests:

```bash
pip install -e ".[test]"
pytest -q
```

CI runs tests on pushes and pull requests. Keep broker credentials, activation secrets, API tokens and `.env` files out of GitHub.

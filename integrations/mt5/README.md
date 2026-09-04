# NodeTrade MT5 EA integration

This directory contains the MT5-side bridge. The EA is intentionally a transport/execution adapter; the NodeTrade Python core remains responsible for prediction, scenarios, opportunity selection, risk policy, and feedback design.

## Flow

`MT5 market/account state -> authenticated HTTPS -> NodeTrade API -> NodeTradeEngine -> signal -> EA validation -> optional MT5 execution -> trade transaction feedback`

## Setup

1. Run the NodeTrade API with the `server` extra.
2. Put the API behind HTTPS. Do not expose the development server directly to the public internet.
3. Set `NODETRADE_LICENSE_SECRET` on the server; never commit it.
4. Provision an account/license in the server-side license store using an administrative provisioning tool (to be added before multi-user production rollout).
5. In MT5, add the exact API origin to **Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL**.
6. Compile `NodeTradeEA.mq5` with the MetaEditor version shipped with the target MT5 terminal.
7. Start with `InpLiveTrading=false` and validate data, authentication, signal freshness, and transaction handling on a demo account.

## Important execution rule

The EA defaults to `InpLiveTrading=false`. The current server response does not yet expose broker-specific lot sizing, and therefore the EA must not be treated as production-ready for unattended live execution merely because the file compiles. Before enabling live trading, the bridge must send symbol contract data (tick size/value, volume min/max/step, stop/freeze levels, margin mode) and receive a server-calculated, validated volume consistent with NodeTrade risk policy.

## Protocol

`POST /v1/analyze` accepts account/license identity, symbol, bid/ask, equity and a bounded OHLCV history. The server authenticates the account and calls the existing `NodeTradeEngine` without changing its decision architecture.

The production protocol should additionally include:

- deterministic signal ID / idempotency key;
- server timestamp and signal age/expiry;
- terminal/account/broker identifiers;
- day-start equity and open-risk state;
- symbol contract specification;
- current positions and pending orders;
- model/version identifier;
- explicit execution permission;
- trade-result feedback endpoint;
- heartbeat/session state;
- replay/duplicate protection.

## Security

- Use HTTPS only.
- Never send MT5 or broker passwords to NodeTrade.
- Treat the activation code as a secret; never log it.
- Bind licenses to the intended MT5 account ID.
- Rate-limit authentication and analysis requests.
- Revoke licenses server-side when needed.
- Store only a keyed hash of activation codes.
- Keep production secrets outside Git.

## Recovery requirements

After EA/VPS/MT5 restart, reconcile the actual MT5 positions and orders before requesting a new actionable signal. `WAIT` must result in no order. A signal must never be executed twice because of a timeout or reconnect. Order acceptance must be determined from MT5 trade-server retcodes and subsequent transaction state, not from a local boolean alone.

## NodeTrade concept preservation

Do not replace the core strategy with a simpler indicator EA. The bridge must preserve the existing causal, predictive, scenario-based and adaptive loop:

`predict -> observe -> update -> execute -> recalculate`

The EA is not the AI brain; it is the authenticated MT5 boundary.

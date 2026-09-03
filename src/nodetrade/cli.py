from __future__ import annotations

import argparse
import json

from .backtest import run_backtest
from .data import load_csv
from .engine import NodeTradeEngine
from .monitoring import performance_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="nodetrade")
    sub = parser.add_subparsers(dest="command", required=True)
    signal = sub.add_parser("signal", help="analyze the latest market state from CSV")
    signal.add_argument("csv")
    backtest = sub.add_parser("backtest", help="run the event-driven backtest")
    backtest.add_argument("csv")
    backtest.add_argument("--equity", type=float, default=100.0)
    args = parser.parse_args()

    candles = load_csv(args.csv)
    if args.command == "signal":
        print(json.dumps(NodeTradeEngine().analyze(candles).to_dict(), indent=2, default=str))
    else:
        results = run_backtest(candles, initial_equity=args.equity)
        print(json.dumps(performance_report(results), indent=2, default=str))


if __name__ == "__main__":
    main()

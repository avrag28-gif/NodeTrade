from __future__ import annotations

import argparse
import os
import secrets
import time

from nodetrade.api import LicenseStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a NodeTrade MT5 account license locally.")
    parser.add_argument("account_id")
    parser.add_argument("--activation-key", default=None)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--db", default=os.getenv("NODETRADE_DB", "nodetrade.db"))
    args = parser.parse_args()

    secret = os.getenv("NODETRADE_LICENSE_SECRET")
    if not secret:
        raise SystemExit("NODETRADE_LICENSE_SECRET is required")
    if args.days <= 0:
        raise SystemExit("--days must be > 0")

    activation_key = args.activation_key or ("NT-" + secrets.token_urlsafe(18))
    expires_at = int(time.time()) + args.days * 86400
    LicenseStore(args.db).provision(args.account_id, activation_key, secret, expires_at)
    print(f"account_id={args.account_id}")
    print(f"activation_key={activation_key}")
    print(f"expires_at={expires_at}")
    print("Store the activation key securely; do not commit it to Git.")


if __name__ == "__main__":
    main()

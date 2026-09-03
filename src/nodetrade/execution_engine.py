from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: Side
    quantity: float
    stop: float | None = None
    target: float | None = None
    client_id: str = ""


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: Side
    quantity: float
    price: float


class BrokerAdapter(Protocol):
    def submit(self, order: OrderRequest, bid: float, ask: float) -> Fill: ...
    def close(self, symbol: str, bid: float, ask: float) -> Fill | None: ...


class PaperBroker:
    """Deterministic broker adapter for integration testing and paper trading."""

    def __init__(self):
        self._seq = 0
        self.positions: dict[str, float] = {}

    def submit(self, order: OrderRequest, bid: float, ask: float) -> Fill:
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")
        self._seq += 1
        price = ask if order.side == Side.BUY else bid
        signed = order.quantity if order.side == Side.BUY else -order.quantity
        self.positions[order.symbol] = self.positions.get(order.symbol, 0.0) + signed
        return Fill(f"paper-{self._seq}", order.symbol, order.side, order.quantity, price)

    def close(self, symbol: str, bid: float, ask: float) -> Fill | None:
        position = self.positions.get(symbol, 0.0)
        if position == 0:
            return None
        self._seq += 1
        side = Side.SELL if position > 0 else Side.BUY
        qty = abs(position)
        price = bid if side == Side.SELL else ask
        self.positions[symbol] = 0.0
        return Fill(f"paper-{self._seq}", symbol, side, qty, price)

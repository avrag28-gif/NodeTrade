from nodetrade.execution_engine import OrderRequest, PaperBroker, Side


def test_paper_broker_fills_and_closes():
    broker = PaperBroker()
    fill = broker.submit(OrderRequest("XAUUSD", Side.BUY, 0.1), 2500.0, 2500.2)
    assert fill.price == 2500.2
    assert broker.positions["XAUUSD"] == 0.1
    close = broker.close("XAUUSD", 2500.1, 2500.3)
    assert close is not None
    assert close.side == Side.SELL
    assert broker.positions["XAUUSD"] == 0.0

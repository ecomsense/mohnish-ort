# SDK: External API Contracts

## broker-ai (RestApi → Fake)

Current backend is `broker_ai.fake.fake.Fake` (development/paper broker).

```python
# Broker base (broker_ai.base.Broker)
order_place(symbol: str, side: str, order_type: str = "MARKET",
            quantity: int = 1, **kwargs) -> str
order_modify(order_id: str, **kwargs) -> str
order_cancel(order_id: str) -> str
authenticate() -> bool

# Properties
orders   -> List[Dict]
positions -> List[Dict]
trades   -> List[Dict]
```

## Websocket (broker_ai.delta.wsocket.Wsocket)

```python
Wsocket(api_key: str | None = None, api_secret: str | None = None)
    .connect(threaded=True)    # connects to Delta Exchange WS
    .subscribe(tokens: list[str])
    .unsubscribe(tokens: list[str])
    .disconnect()

    # Properties
    .ltp        -> dict[str, float]    # {symbol_token: price}
    .connected  -> bool

    # Callbacks (set by user)
    .on_connect = lambda: None
    .on_ticks   = lambda ltp: None
    .on_close   = lambda: None
    .on_error   = lambda err: None
```

## Quote Format (Wsocket.ltp)

```json
{"12345": 50000.5, "67890": 150.0}
```

## Order Format (Books.orders)

```json
{"order_id": "123", "status": "COMPLETE", "symbol": "BTC50000CE",
 "quantity": 1, "side": "SELL", "average_price": 150.0}
```

## Position Format (Books.positions)

```json
{"symbol": "BTC50000CE", "quantity": -1, "unrealised": 50.0, "m2m": 0.0}
```

## Constraints

| | |
|--|--|
| Async | NOT supported (sync only) |
| State format | JSON (~0.5ms) |
| Quote source | `ws.ltp` dict (on-demand) |
| Underlying | Token configured in `settings.yml: base_instrument` |
| Python | 3.10 |
| Deps | uv sync, broker-ai(git), toolkit(git), pendulum, pyyaml |

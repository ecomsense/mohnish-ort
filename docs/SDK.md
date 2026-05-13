# SDK: External API Contracts

## broker-ai (via RestApi)

```python
order_place(symbol: str, side: str, order_type: str, quantity: int,
            trigger_price: float | None = None, price: float | None = None,
            tag: str | None = None) -> str            # returns order_id

order_modify(order_id: str, order_type: str, price: float) -> None

ticker() -> object
  .on_ticks(callable)          # set callback
  .subscribe(tokens: List[int])
  .set_mode(token, mode)
  .connect(threaded=True)

# return type
trades -> List[Dict]
orders -> List[Dict]
positions -> List[Dict]
```

## Quote Format (Wserver._ltp)

```json
[{"instrument_token": 12345, "last_price": 50000.5}]
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
| Quote sub | On-demand via OrderManager |
| Underlying sub | Once in Engine |
| Python | 3.10 |
| Deps | uv sync, broker-ai(git), toolkit(git), pendulum, pyyaml |

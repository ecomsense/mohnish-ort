# FLOW: Data & Control Flow

## Startup

```
main.py
  ├─ sleep till start time
  ├─ Builder.build() → Coinshort()
  └─ Engine([Coinshort]).run()

Engine.run()
  ├─ Wsocket() ← connects to Delta Exchange WS
  ├─ Books() ← initializes broker API
  └─ while not stop:
       for each strategy:
         strategy.tick(ws, books)
```

## Tick Cycle

```
Coinshort.tick(ws, books)
  │
  ├─ 1. underlying_price = ws.ltp(underlying_token)
  │
  ├─ 2. intents = compute_intents(state, underlying_price, books)
  │     ├─ T1: check each leg's orders for completion
  │     ├─ T2: check underlying vs bounds
  │     └─ apply interlock filter
  │
  ├─ 3. for intent in intents:
  │      OrderManager.execute(intent, underlying_price)
  │        ├─ resolve symbol → strike lookup
  │        ├─ subscribe quote → ws.subscribe([token])
  │        ├─ wait for quote → _get_quote(token, 500ms)
  │        └─ place orders → order_place(SELL) + order_place(SL)
  │
  ├─ 4. update_state(intent, result)
  │
  └─ 5. save_state() → JSON to disk
```

## Order Placement Detail

```
OrderManager._enter_short(strike, option_type)
  symbol = OptionSymbol.build(strike, option_type)  # "BTC52000CE"
  token  = OptionSymbol.get_token(symbol)
  ws.subscribe([token])

  price = wait for WS tick → timeout 500ms

  short_id = api.order_place(symbol, "SELL", "MARKET", qty)
  sl_id    = api.order_place(symbol, "BUY", "SL", qty*2,
                              trigger_price=price+SL,
                              price=price+SL+slippage)

  return ExecutionResult(short_id, sl_id, price, strike)
```

## State Machine Visual

```
         INITIAL ENTRY (SHORT CE + SHORT PE)
                    │
         ┌──────────┴──────────┐
         │                     │
    CE SL hit            PE SL hit
         │                     │
    CE=LONG               PE=LONG
    PE=SHORT              CE=SHORT
         │                     │
    ┌────┼────┐           ┌────┼────┐
    │    │    │           │    │    │
  SL   TGT  TTL        SL   TGT  TTL
    │    │    │           │    │    │
  SHORT SFTD FLAT      SHORT SFTD FLAT
         │                     │
         └──────────┬──────────┘
                    │
             T2 trigger (underlying
             crosses bound + leg=LONG)
                    │
             T_upper or T_lower protocol
             (shift opposite leg)
```

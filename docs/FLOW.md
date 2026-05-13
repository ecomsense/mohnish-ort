# FLOW: Data & Control Flow

## Startup

```
main.py
  ├─ ensure_paths(), init_logging()
  ├─ Builder.build()
  │     ├─ reads config + symbols from CNFG
  │     ├─ creates OptionSymbol, RestApi
  │     └─ returns Coinshort(config, symbols, api)
  └─ Engine([Coinshort]).run()

Engine.run()
  ├─ Books() ← wraps broker API
  ├─ Wsocket(api_key, api_secret) ← connects to Delta Exchange WS
  └─ while not stop:
       for each strategy:
         strategy.tick(ws, books)
       blink()
```

## Tick Cycle (current — stubs)

```
Coinshort.tick(ws, books)
  │
  ├─ 1. bn_ltp = ws.ltp.get(str(underlying_token))
  │      if bn_ltp == 0: return
  │
  ├─ 2. for each leg (CE, PE):
  │      if SHORT and SL order COMPLETE → flip to LONG
  │      if LONG → stub (TTL/OOB not implemented)
  │
  ├─ 3. if underlying crosses bound + leg is LONG:
  │      tier += 1, run T2 protocol (stub)
  │
  └─ 4. save_state() → JSON to disk
```

## Target Tick Cycle (with OrderManager)

```
Coinshort.tick(ws, books)
  │
  ├─ 1. underlying_price = ws.ltp.get(str(underlying_token))
  │
  ├─ 2. intents = compute_intents(state, underlying_price, books)
  │     ├─ T1: per-leg (SL, target, TTL)
  │     ├─ T2: underlying crosses bound + leg=LONG
  │     └─ apply interlock filter
  │
  ├─ 3. for intent in intents:
  │      OrderManager.execute(intent, underlying_price)
  │        ├─ resolve symbol → strike lookup
  │        ├─ subscribe quote → ws.subscribe([token])
  │        └─ place orders → order_place(SELL) + order_place(SL)
  │
  ├─ 4. update_state(intent, result)
  │
  └─ 5. save_state() → JSON to disk
```

## Order Placement Detail

```
OrderManager._enter_short(strike, option_type)
  symbol = build_symbol(strike, option_type)
  token  = get_token(symbol)
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

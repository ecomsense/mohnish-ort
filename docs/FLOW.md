# FLOW: Data & Control Flow

## Startup

```
main.py
  ├─ ensure_paths()              # create data/ dir, copy settings if missing
  ├─ init_logging()              # AsyncLogger (console or file)
  ├─ wait(entry_time)            # sleep until configured start time
  │
  ├─ Wsocket(api_key, api_secret) → ws.connect(threaded=True)
  ├─ config = CNFG["strategy"]
  ├─ base   = CNFG["base_instrument"]
  ├─ Symbol(exchange="DELTA", symbol="BTC", data_path=S_DATA)
  ├─ Restapi(config["quantity"])
  ├─ Builder.build(config, symbols, api, ws, underlying_token, symbol)
  │     ├─ OrderManager(ws, symbols, api, config)
  │     └─ Coinshort(config, symbols, api, om, token, symbol)
  │           └─ load_state() + _resubscribe_tokens()
  │
  └─ Engine(strategy, ws, underlying_token).run()
        ├─ ws.subscribe([underlying_token])
        └─ while True:
             price = ws.ltp.get(token)
             strategy.tick(price)
             blink()
```

## Tick Cycle

```
Coinshort.tick(underlying_price)
  │
  ├─ 1. if price == 0: return
  │
  ├─ 2. if bounds empty:
  │      ├─ _enter_straddle() → OM.enter_short(CE) + OM.enter_short(PE)
  │      └─ _finalize_entry() → calc premium, set bounds
  │
  ├─ 3. for each leg (CE, PE): OM.manage_leg(opt, price)
  │      ├─ SHORT + SL complete → BUY MARKET (close short) + BUY MARKET (open long) + place SELL SL
  │      ├─ LONG + target hit → modify SELL SL→MARKET, enter_short(new ATM)
  │      ├─ LONG + TTL + profit → modify SELL SL→MARKET, enter_short(new ATM)
  │      ├─ LONG + SL complete → enter_short(new ATM)
  │      └─ SHIFTED + SL complete → FLAT
  │
  ├─ 4. for each satellite: SHIFTED + SL complete → FLAT
  │
  ├─ 5. T2 check: bound breached + stretched leg LONG → tier++, satellite protocol
  │
  └─ 6. save_state() → JSON to disk
```

## SAR Cycle Detail (qty=1)

```
SHORT (sold 1 contract)
  ├─ BUY SL at entry + stop_loss (qty=1)
  │
  ├─ SL triggers → BUY fills 1 (close short)
  │            → BUY MARKET 1 (open long) via explicit enter_long
  │            → place SELL SL for long (qty=1)
  │
  ├─ LONG →
  │    ├─ target/TTL → modify SELL SL→MARKET → exits long
  │    │            → enter_short(new ATM strike)
  │    └─ SL triggers → SELL fills 1 (close long)
  │                 → enter_short(new ATM strike)
  │
  └─ SHORT again at new strike
```

## T2 Protocol

```
Bound breach + stretched leg LONG:
  ├─ _close_satellite(tier-2, counter_leg) → modify SL→MARKET
  ├─ enter_short(underlying, counter_leg) → adds to satellites[]
  └─ bounds.append([price + premium/2, price - premium/2])
```

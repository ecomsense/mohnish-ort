# SPEC: mohnish-ort (Coinshort Strategy)

## Documents

| File | What it covers |
|------|----------------|
| [SPEC.md](SPEC.md) | Entry point: arch, files, gaps |
| [DESIGN.md](docs/DESIGN.md) | Data structures, interfaces, state transitions |
| [SDK.md](docs/SDK.md) | External API contracts, constraints |
| [FLOW.md](docs/FLOW.md) | Data flow, lifecycle, order placement |

## Overview
Automated trading system for Delta Exchange India. BTC monthly options. Short straddle with Rolling SAR and T-Series Action Zones.

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              main.py                                       │
│  ensure_paths() → init_logging() → wait(entry_time)                        │
│  Wsocket() → Symbol() → Restapi() → Builder.build() → Engine().run()      │
└──────────────────────────┬─────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────────────┐
│  Builder.build()                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  OrderManager(ws, symbols, api, config) → Coinshort(config, ...)     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬─────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────────────┐
│  Engine.run()                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  ws.subscribe([underlying_token])                                    │  │
│  │  while True:                                                         │  │
│  │    price = ws.ltp.get(token, 0.0)                                    │  │
│  │    strategy.tick(price)                                              │  │
│  │    blink()                                                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬─────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────────────┐
│  Coinshort.tick(underlying_price)                                          │
│                                                                           │
│  ┌─ ENTRY PHASE (bounds empty) ────────────────────────────────────────┐  │
│  │  if _entry_ce_id is None:  _enter_straddle(price)                   │  │
│  │    ├─ OM.enter_short(price, "CE") → store ce_id, pe_id             │  │
│  │    └─ OM.enter_short(price, "PE")                                   │  │
│  │  elif both orders complete: _finalize_entry(price)                   │  │
│  │    ├─ get fill prices → calc premium                                │  │
│  │    ├─ bounds = [price+premium, price-premium]                       │  │
│  │    └─ ce.status=SHORT, pe.status=SHORT                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─ LEG MANAGEMENT (bounds exist) ─────────────────────────────────────┐  │
│  │  for each leg (CE, PE): OM.manage_leg(opt, price)                   │  │
│  │                                                                      │  │
│  │  OrderManager.manage_leg(opt, price):                                │  │
│  │    opt_price = ws.ltp.get(token)                                     │  │
│  │                                                                      │  │
│  │    SHORT ── SL hit? ──→ LONG (place sell SL at entry - stop_loss)   │  │
│  │         no ───────────────────────────────────► stay SHORT           │  │
│  │                                                                      │  │
│  │    LONG ── target hit? ──→ modify SL→MARKET, enter_short(same type) │  │
│  │         ├── TTL + profit? ──→ same shift-strike flow                │  │
│  │         └── SL hit? ──→ flip to SHORT, enter_short(same type)       │  │
│  │                                                                      │  │
│  │    SHIFTED ── SL hit? ──→ FLAT                                      │  │
│  │                                                                      │  │
│  │  for each satellite:                                                 │  │
│  │    SHIFTED + SL hit ──→ FLAT                                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─ T2 TIER PROTOCOL ──────────────────────────────────────────────────┐  │
│  │  if price >= upper AND ce.status == LONG:                            │  │
│  │    tier += 1                                                         │  │
│  │    t_upper_protocol(price)                                           │  │
│  │      ├─ skip if satellite exists for this tier                       │  │
│  │      ├─ _close_satellite(tier - 2)                                   │  │
│  │      ├─ OM.enter_short(price, "PE") → append to satellites[]        │  │
│  │      └─ bounds.append([price+premium, price-premium])                │  │
│  │                                                                      │  │
│  │  if price <= lower AND pe.status == LONG:                            │  │
│  │    tier += 1                                                         │  │
│  │    t_lower_protocol(price)                                           │  │
│  │      ├─ skip if satellite exists for this tier                       │  │
│  │      ├─ _close_satellite(tier - 2)                                   │  │
│  │      ├─ OM.enter_short(price, "CE") → append to satellites[]        │  │
│  │      └─ bounds.append([price+premium, price-premium])                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─ PERSISTENCE ───────────────────────────────────────────────────────┐  │
│  │  save_state() → coinshort_state.json (tier, bounds, premium,        │  │
│  │    ce/pe state, satellites, entry_time)                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────────────┐
│  OrderManager.enter_short(underlying_price, option_type)                   │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  row = symbols.filter_by_moneyness(price, 0, option_type)            │  │
│  │  token = row["ws_token"]                                             │  │
│  │  ws.subscribe([token])                                               │  │
│  │  price = ws.ltp.get(token)  ← wait for quote                         │  │
│  │                                                                      │  │
│  │  short_id = api.enter({symbol, side=SELL, order_type=MARKET})        │  │
│  │  sl_id    = api.enter({symbol, side=BUY,  order_type=SL,             │  │
│  │                         trigger_price=price+stop_loss,               │  │
│  │                         price=price+stop_loss+slippage})             │  │
│  │                                                                      │  │
│  │  return {symbol, token, strike, price, short_id, sl_id}              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Role |
|------|------|
| `src/main.py` | Entry point |
| `src/core/build.py` | Strategy construction |
| `src/core/engine.py` | Tick loop orchestrator |
| `src/strategies/coinshort.py` | Strategy logic |
| `src/constants.py` | Config + logger |
| `src/sdk/restapi.py` | Restapi (Delta broker wrapper) |
| `broker_ai.delta.wsocket` | Websocket ticker (from broker-ai dep) |
| `broker_ai.delta.symbols` | Symbol resolution (from broker-ai dep) |
| `src/sdk/models.py` | Data models |
| `factory/settings.yml` | Strategy config |

## Known Issues

### Bugs

- [ ] B1: `_close_satellite(tier=1)` always closes PE — on lower breach at T3, CE should close instead
- [ ] B2: `_entry_ce_id` / `_entry_pe_id` not persisted — crash during straddle entry causes double-entry on restart
- [ ] B3: SL modification on target/TTL hit (`order_modify` to MARKET) races with SL trigger — cancel-first pattern needed

### Design

- [ ] D1: `manage_leg` reads `opt_price` but never uses it in SHORT→LONG path — dead read
- [x] D2: Replaced `__import__` with `_option_type()` helper + `Calls` import in `order_manager.py`
- [ ] D3: `_close_satellite(tier=1)` logic assumes PE is always the T1 side to close (tied to B1)

### Code Quality

- [x] Q1: `sdk/utils.py` imports `S_DATA` and `O_FUTL` from `constants.py` instead of duplicating
- [x] Q2: `requirements.txt` removed — deps managed solely through `pyproject.toml`
- [ ] Q3: No `AGENTS.md` with troubleshooting checklist
- [x] Q4: ruff config added to `pyproject.toml` (py310, E/F/I/N/W, line-length 120)

### Done

- [x] State YAML → JSON
- [x] Logger init at import time (moved to `main.py`)
- [x] Logger crash on failure (no silent fallback)
- [x] `show` semantics (true=console, false=file)
- [x] Websocket moved to `broker_ai.delta.wsocket.Wsocket`
- [x] DI: Coinshort receives config + deps via constructor (Builder builds them)
- [x] OrderManager — resolves symbols, subscribes quotes, places orders
- [x] Delta broker wired (replaces Fake)
- [x] T1 entry + full SAR cycle (SHORT↔LONG, target exit, TTL, 24 tests)
- [x] T2/T-2 protocols (shift opposite leg, per-tier bounds, SHIFTED state)

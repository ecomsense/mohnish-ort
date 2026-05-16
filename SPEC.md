# SPEC: mohnish-ort (Coinshort Strategy)

## Documents

| File | What it covers |
|------|----------------|
| [SPEC.md](SPEC.md) | Entry point: arch, files, status |
| [TRADER_INTENT.md](docs/TRADER_INTENT.md) | Strategy behavior, trader expectations |
| [INTENT_VS_CODE.md](docs/INTENT_VS_CODE.md) | Gap analysis, bug status |
| [SDK.md](docs/SDK.md) | External API contracts, constraints |
| [DESIGN.md](docs/DESIGN.md) | Data structures, state transitions |
| [FLOW.md](docs/FLOW.md) | Data flow, lifecycle, order placement |

## Overview
Automated trading system for Delta Exchange India. BTC monthly options. Short straddle with Rolling SAR and T-Series Action Zones.

## Architecture

```
main.py → Builder.build() → Engine.run()
               │
               ├── OrderManager(ws, symbols, api, config)
               │     └── enter_short() → SELL MARKET + BUY SL
               │
               └── Coinshort(config, ...).tick(price)
                     ├── Entry: _enter_straddle() → _finalize_entry()
                     ├── SAR: manage_leg() per leg (SHORT↔LONG↔SHIFTED)
                     └── T2: bound breach + leg LONG → sell counter-leg satellite
```

## Key Files

| File | Role |
|------|------|
| `src/main.py` | Entry point |
| `src/core/build.py` | Strategy construction |
| `src/core/engine.py` | Tick loop orchestrator |
| `src/strategies/coinshort.py` | Strategy logic |
| `src/sdk/order_manager.py` | Order placement, leg management |
| `src/sdk/restapi.py` | Delta broker wrapper |
| `src/sdk/models.py` | Data models (Calls, Puts, LegState) |
| `src/backtest_live.py` | Real-price backtest (1m candles, real option data) |
| `src/download_1m.py` | Download 1m option candle data |
| `factory/settings.yml` | Strategy config |

## Backtest Results (May 29 options, 1m candles, real prices)

| Metric | Value |
|--------|-------|
| Period | Apr 25 → May 16 |
| Entry | May 2 @ 78304 |
| Final tier | T2 (T2 breach May 5) |
| Realized P&L | +822 per BTC |
| MTM P&L | +4845 per BTC |
| Total P&L | +5667 per BTC (= 5.67 USD/contract) |

## Status

### Fixed Bugs

- [x] B1: `_close_satellite(tier=1)` always closed PE — now dispatches via `counter_leg` param
- [x] B2: `_entry_ce_id` / `_entry_pe_id` not persisted — added to save/load state
- [x] B3: `order_modify` races with SL trigger — not a bug, `order_modify` is correct per "never cancel" discipline
- [x] SL quantity was `qty * 2` — changed to `qty=1`, SAR uses explicit MARKET BUY for long entry

### Known Design Items

- [ ] D1: `manage_leg` reads `opt_price` but never uses it in SHORT→LONG path — dead read
- [ ] D3: `_close_satellite(tier=1)` logic tied to `counter_leg` dispatch (fixed B1)

### Code Quality

- [x] Q1-Q4: Imports, deps, ruff config, AGENTS.md — resolved

# SPEC: mohnish-ort (Coinshort Strategy)

## Overview
Automated trading system for Delta Exchange India. BTC monthly options. Short straddle with Rolling SAR and T-Series Action Zones.

## Architecture

```
┌─────────────┐
│   main.py   │  sleep → build → run
└──────┬──────┘
       │
┌──────▼──────┐
│   Builder   │  Coinshort()
└──────┬──────┘
       │
┌──────▼──────┐
│   Engine    │  while not stop: s.tick(ws, books)
└──────┬──────┘
       │
┌──────▼──────────┐
│   Coinshort     │  read state → decide intents → execute
└─────────────────┘
```

## Key Files

| File | Role |
|------|------|
| `src/main.py` | Entry point |
| `src/core/build.py` | Strategy construction |
| `src/core/engine.py` | Tick loop orchestrator |
| `src/strategies/coinshort.py` | Strategy logic |
| `src/constants.py` | Config + logger |
| `src/sdk/helper.py` | RestApi (broker wrapper) |
| `broker_ai.delta.wsocket` | Websocket ticker (Delta Exchange) |
| `src/sdk/books.py` | Order/position queries |
| `src/sdk/symbol.py` | Symbol resolution |
| `src/sdk/models.py` | Data models |
| `factory/settings.yml` | Strategy config |

## Known Issues

### Implement (stubs)

- [ ] Coinshort.initial_entry() is `pass`
- [ ] TTL/OOB logic in tick() stubbed
- [ ] T2 protocols (t_upper/lower) not ported to tick pattern
- [ ] cleanup() is stub
- [ ] No OrderManager separation
- [ ] Intent protocol not in code
- [ ] Interlock rules not implemented

### Bugs

- [ ] B1: `sdk/helper.py` — `Fake.__init__` references `self.cols` but never defines it. Crashes on `order_place`.
- [ ] B3: `strategies/coinshort.py` — `set_bounds` accesses `buy_params["price"]` without key check. May KeyError.

### Design

### Code Quality

- [ ] Q2: `ensure_paths()` creates log dir but not `S_DATA` for state files.

### Done

- [x] State YAML → JSON
- [x] Logger init at import time (moved to `main.py`)
- [x] Logger crash on failure (no silent fallback)
- [x] `show` semantics (true=console, false=file)
- [x] Websocket moved to `broker_ai.delta.wsocket.Wsocket`
- [x] DI: Coinshort receives config + deps via constructor (Builder builds them)

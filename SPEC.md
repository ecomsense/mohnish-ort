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
┌─────────────┐
│   main.py   │  sleep → build → run
└──────┬──────┘
       │
┌──────▼──────┐
│   Builder   │  Coinshort()
└──────┬──────┘
       │
┌──────▼──────┐
│   Engine    │  while not stop: strategy.tick(ws)
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
| `broker_ai.delta.wsocket` | Websocket ticker (from broker-ai dep) |
| `broker_ai.delta.symbols` | Symbol resolution (from broker-ai dep) |
| `src/sdk/models.py` | Data models |
| `factory/settings.yml` | Strategy config |

## Known Issues

### Implement (stubs)

- [ ] Coinshort.initial_entry() is `pass`
- [ ] TTL/OOB logic in tick() stubbed
- [ ] T2 protocols (t_upper/lower) not ported to tick pattern
- [ ] cleanup() is stub
- [ ] Intent protocol not in code
- [ ] Interlock rules not implemented

### Bugs

- [ ] B1: `sdk/helper.py` — `Fake.__init__` references `self.cols` but never defines it. Crashes on `order_place`.
- [ ] B3: `strategies/coinshort.py` — `set_bounds` accesses `buy_params["price"]` without key check. May KeyError.

### Design

*None — all resolved.*

### Code Quality

- [ ] Q2: `ensure_paths()` creates log dir but not `S_DATA` for state files.

### Done

- [x] State YAML → JSON
- [x] Logger init at import time (moved to `main.py`)
- [x] Logger crash on failure (no silent fallback)
- [x] `show` semantics (true=console, false=file)
- [x] Websocket moved to `broker_ai.delta.wsocket.Wsocket`
- [x] DI: Coinshort receives config + deps via constructor (Builder builds them)
- [x] OrderManager — resolves symbols, subscribes quotes, places orders

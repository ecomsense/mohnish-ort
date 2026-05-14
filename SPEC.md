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
| `src/sdk/restapi.py` | Restapi (Delta broker wrapper) |
| `broker_ai.delta.wsocket` | Websocket ticker (from broker-ai dep) |
| `broker_ai.delta.symbols` | Symbol resolution (from broker-ai dep) |
| `src/sdk/models.py` | Data models |
| `factory/settings.yml` | Strategy config |

## Known Issues

### Implement (stubs)

- [ ] TTL/OOB logic in tick() stubbed
- [ ] T2 protocols (t_upper/lower) not ported to tick pattern
- [ ] cleanup() is stub
- [ ] Interlock rules not implemented

### Bugs

*None — all resolved.*

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
- [x] Delta broker wired (replaces Fake)
- [x] T1 entry (ATM straddle + bound calculation, 16 tests)

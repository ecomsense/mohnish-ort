# SPEC: mohnish-ort (Delta Strategy)

## Documents

| File | What it covers |
|------|----------------|
| [SPEC.md](SPEC.md) | Entry point: arch, files, gaps |
| [DESIGN.md](docs/DESIGN.md) | Data structures, interfaces, state shape |
| [RULES.md](docs/RULES.md) | State machines: T1, T2, interlock |
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
│   Builder   │  Delta()
└──────┬──────┘
       │
┌──────▼──────┐
│   Engine    │  while not stop: s.tick(ws, books)
└──────┬──────┘
       │
┌──────▼──────┐
│   Delta     │  read state → decide intents → execute
└─────────────┘
```

## Key Files

| File | Role |
|------|------|
| `src/main.py` | Entry point |
| `src/core/build.py` | Strategy construction |
| `src/core/engine.py` | Tick loop orchestrator |
| `src/strategies/delta.py` | Strategy logic |
| `src/constants.py` | Config + logger |
| `src/sdk/helper.py` | RestApi (broker wrapper) |
| `src/sdk/wserver.py` | Websocket ticker |
| `src/sdk/books.py` | Order/position queries |
| `src/sdk/symbol.py` | Symbol resolution |
| `src/sdk/models.py` | Data models |
| `src/sdk/signals.py` | Signal functions |
| `factory/settings.yml` | Strategy config |

## Known Issues

- [ ] Delta.initial_entry() is `pass`
- [ ] TTL/OOB logic stubbed
- [ ] T2 protocols not ported to tick pattern
- [ ] cleanup() stubbed
- [ ] No OrderManager separation
- [ ] State uses YAML, should be JSON
- [ ] Intent protocol not in code
- [ ] Interlock rules not implemented
- [ ] No unit tests

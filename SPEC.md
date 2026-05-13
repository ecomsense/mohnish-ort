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
| `broker_ai.delta.wsocket` | Websocket ticker (Delta Exchange) |
| `src/sdk/books.py` | Order/position queries |
| `src/sdk/symbol.py` | Symbol resolution |
| `src/sdk/models.py` | Data models |
| `factory/settings.yml` | Strategy config |

## Known Issues

### Implement (stubs)

- [ ] Delta.initial_entry() is `pass`
- [ ] TTL/OOB logic in tick() stubbed
- [ ] T2 protocols (t_upper/lower) not ported to tick pattern
- [ ] cleanup() is stub
- [ ] No OrderManager separation
- [ ] Intent protocol not in code
- [ ] Interlock rules not implemented

### Bugs

- [ ] B1: `sdk/helper.py` — `Fake.__init__` references `self.cols` but never defines it. Crashes on `order_place`.
- [ ] B3: `strategies/delta.py:139` — `set_bounds` accesses `buy_params["price"]` without key check. May KeyError.

### Design

- [ ] D2: `pyproject.toml` lists `pyopenssl`, `setuptools`, `wheel` as runtime deps — build tools only.
- [ ] D3: Delta reads directly from global `CNFG` — no DI, hard to unit test.

### Code Quality

- [ ] Q1: `sdk/helper.py` — `log = get_logger(__name__)` before `from sdk.models import Order`. Non-standard import order.
- [ ] Q2: `ensure_paths()` creates log dir but not `S_DATA` for state files.
- [ ] Q3: `sdk/books.py:29` — `is_order_complete` hardcodes `"COMPLETE"` string. Broker-dependent.
- [ ] Q4: `core/build.py` — `symbol_settings` variable assigned but never passed to Delta.

### Done

- [x] State YAML → JSON
- [x] Logger init at import time (moved to `main.py`)
- [x] Logger crash on failure (no silent fallback)
- [x] `show` semantics (true=console, false=file)
- [x] Websocket moved to `broker_ai.delta.wsocket.Wsocket`

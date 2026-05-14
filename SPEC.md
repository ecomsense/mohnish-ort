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

### Bugs

- [ ] B1: `_close_satellite(tier=1)` always closes PE — on lower breach at T3, CE should close instead
- [ ] B2: `_entry_ce_id` / `_entry_pe_id` not persisted — crash during straddle entry causes double-entry on restart
- [ ] B3: SL modification on target/TTL hit (`order_modify` to MARKET) races with SL trigger — cancel-first pattern needed

### Design

- [ ] D1: `manage_leg` reads `opt_price` but never uses it in SHORT→LONG path — dead read
- [ ] D2: Repeated `__import__("sdk.models", ...).Calls` in `order_manager.py:134,154,177` — extract helper
- [ ] D3: `_close_satellite(tier=1)` logic assumes PE is always the T1 side to close (tied to B1)

### Code Quality

- [ ] Q1: `sdk/utils.py` duplicates `S_DATA = "../data/"` from `constants.py`
- [ ] Q2: `requirements.txt` still present with `kiteext` dep — remove, use `pyproject.toml` only
- [ ] Q3: No `AGENTS.md` with troubleshooting checklist
- [ ] Q4: No lint config (ruff/mypy) in `pyproject.toml`

### Infra

- [ ] I1: `factory/` directory missing — `ensure_paths()` can't bootstrap settings/symbols on fresh clone

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

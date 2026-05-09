# Gemini CLI Instructions - mohnish-ort

This file provides foundational mandates and repo-wide guidance for the `mohnish-ort` project.

## Project Overview
Automated trading system for Bank Nifty Short Straddle strategy. It uses Kite/ext and custom toolkits for broker interaction and signal processing.

## Architecture
- **Language:** Python 3.x
- **Core Frameworks:** Pydantic, PyYAML, Pandas, Pendulum
- **External Dependencies:** `broker-ai`, `kiteext`, `toolkit` (internal/custom repos)
- **Entry Point:** `src/main.py`

## Conventions
- **Code Style:** Follow PEP 8. Use type hints for function signatures.
- **Logging:** Use the logger defined in `src/constants.py`.
- **Configuration:** All strategy settings should be in `factory/settings.yml`. Symbol-specific data in `factory/symbols.yml`.
- **Error Handling:** Use try-except blocks with `traceback.print_exc()` for critical paths.

## Key Workflows
1. **Strategy Entry:** Handled in `Both` or `Oneside` classes in `src/both.py` or `src/oneside.py`.
2. **WebSocket Feed:** Managed by `Wsocket` in `src/wsocket.py`.
3. **API Interactions:** Abstracted through `Helper` in `src/api.py`.

## Directories
- `src/`: Core source code.
- `factory/`: YAML/CSV configuration and signal files.
- `.git/`: Source control.

## Testing
(TBD - Search for existing tests if any, otherwise add tests for new features)

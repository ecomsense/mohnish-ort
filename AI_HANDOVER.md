# AI Handover Document: mohnish-ort

This document is designed to provide a comprehensive technical state-of-the-art summary for any AI tool to quickly pick up development on this project.

## Project Purpose
Automated trading of Bank Nifty options using a Short Straddle strategy.

## Technical Stack
- **Python**: 3.10 (Pinned via `uv`).
- **Dependency Management**: `uv` is used. Run `uv sync` to install.
- **Data Handling**: `pandas` for signal processing, `PyYAML` for configuration.
- **Pydantic**: Version 2.x for configuration and model validation.

## Core Components

### 1. Entry & Orchestration
- **`src/main.py`**: The **Composition Root**. It initializes `core_config`, sets up global logging, and injects validated settings into strategy classes via Dependency Injection.
- **`src/strategies/both.py`**: Implements the `Both` class. Now receives `config` and `logging` via its constructor.
- **`src/strategies/oneside.py`**: Implements the `Oneside` class. Now receives `config` and `logging` via its constructor.

### 2. Market Data & Symbols
- **`src/wsocket.py`**: Handles real-time LTP updates. Now explicitly receives its dependencies (config, symbols, logging, helper).
- **`src/symbols.py`**: Manages instrument tokens. Decoupled from global state.

### 3. Execution & Signals
- **`src/integrations/api.py`**: Contains `Helper` class. Uses Dependency Injection for broker credentials and logging.
- **`src/core/config.py`**: (Updated) Replaces legacy `constants.py`. Uses Pydantic for core setting validation.

### 4. Configuration & Resources
- **`src/resources/`**: (NEW) Replaces the external `factory/` folder. Contains strategy templates (`settings.yml`) and symbol definitions (`symbols.yml`).
- **`mohnish-ort.yml`**: Contains broker-specific credentials, automatically merged by `src/core/config.py`.

### 5. Utilities & Scripts
- **Shell Scripts**: `paper.sh`, `show.sh`, `tmux.sh`, etc., provide quick ways to monitor logs or manage execution.
- **`read_file.php`**: Legacy/Utility script for viewing log files via web (points to a specific log path).
- **Batch Files**: `run_algo.bat`, `update.bat` for Windows environments.

## Strategy Logic
1. **Initial Entry**: Sell 1 lot of ATM CE and PE.
2. **Stop Loss**: Set SL for 2 lots (configurable) at X points (default 60).
3. **SL Hit**: If SL is hit, the position becomes a net 1 lot BUY on that side.
4. **Monitoring**: Monitor Bank Nifty and component stocks (HDFC, ICICI, etc.) against S/R levels.
5. **Exit/Adjustment**: Exit the buy position if price crosses S/R levels. Sell another ATM option on the same side with double SL.

## Current State & Recent Changes
- The project appears to be in a functional state for both indices and single-side strategies.
- Recent focus seems to be on supporting SENSEX and other indices as well.

## Developer Notes
- Ensure `requirements.txt` is installed, especially the custom git dependencies.
- The `toolkit` and `kiteext` libraries are essential for order execution.
- Check `factory/settings.yml` before running `src/main.py`.

## Future Roadmap
A detailed refactoring strategy to improve testability, performance, and reliability is available in `REFACTORING_PLAN.md`.


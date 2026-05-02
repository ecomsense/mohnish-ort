# Refactoring Roadmap: mohnish-ort

This document outlines the proposed technical improvements for the `mohnish-ort` project to enhance testability, performance, and reliability.

## 1. Testability Improvements
- **Dependency Injection**: Refactor `Helper`, `Both`, and `Oneside` to accept an API/Broker instance in their constructors. Avoid using the global `Helper.api_object`.
- **Mocking Strategy**: Create a `MockBroker` class that implements the same interface as the Zerodha/Bypass brokers to allow offline strategy testing.
- **Data Decoupling**: Modify `signals.py` and `symbols.py` to accept data streams or file paths as arguments rather than hardcoding paths to the `factory/` folder.

## 2. Performance & Latency Optimization
- **WebSocket Optimization**: 
    - Change `Wsocket._ltp` from a list to a **dictionary** keyed by `instrument_token` for $O(1)$ lookups.
    - Implement `threading.Lock` to ensure thread-safe updates between the WebSocket thread and the main strategy loop.
- **Asynchronous Execution**:
    - Use `asyncio` for placing multi-leg orders (e.g., selling CE and PE simultaneously) to minimize execution slippage.
- **Hot-Path Cleanup**: Reduce logging and redundant attribute lookups (like `vars(opt)`) inside the main `run()` loops.

## 3. Reliability & Edge Case Handling
- **State Management**: Replace integer-based status codes (`0, 1, -1`) with a Python `Enum` (e.g., `TradeStatus`) for better readability and fewer logical errors.
- **Order Handling**:
    - Update `is_order_complete` to explicitly handle `PARTIALLY_FILLED` and `REJECTED` states.
    - Add a retry mechanism with exponential backoff for broker API calls.
- **Graceful Shutdown**: Improve the `finally` block in `Both.run()` to ensure all open orders are cancelled and positions are handled safely even if a critical exception occurs.

## 4. Code Quality
- **Schema Validation**: Expand the use of `pydantic` for validating all configuration files and API responses.
- **Typing**: Complete type hinting across the codebase to enable better static analysis with `mypy`.

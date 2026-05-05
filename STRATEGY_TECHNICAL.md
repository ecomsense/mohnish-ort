# Technical Strategy Specification: Automated Short Straddle & Delta Neutral Execution

## 1. Executive Summary
The `mohnish-ort` system is an algorithmic trading engine designed for high-frequency execution of delta-neutral and directional option selling strategies. Its primary mode of operation is an automated **At-The-Money (ATM) Short Straddle**, optimized for capturing theta decay while managing directional risk through systematic stop-losses and technical price boundaries.

## 2. Strategy Architectures

### 2.1 Delta Neutral: The `Both` Strategy
The `Both` class implements a classic Short Straddle.
*   **Strike Selection:** Dynamically calculates the ATM strike based on the Last Traded Price (LTP) of the underlying index (e.g., BANKNIFTY, SENSEX) using a rounding algorithm (`round(LTP / Strike_Diff) * Strike_Diff`).
*   **Initial Entry:** Executes simultaneous `MARKET SELL` orders for both the Call (CE) and Put (PE) of the nearest expiry.
*   **Inventory Management:** Immediately places `SL-M` (Stop Loss Market) buy-back orders for both legs.

### 2.2 Directional/Bias: The `Oneside` Strategy
Allows for selling either the Call or Put leg individually based on a predefined market bias.
*   **Usage:** Configured via `strategy.type` (-1 for Put only, 1 for Call only).
*   **Execution:** Mirrors the `Both` logic but restricts inventory to a single leg.

## 3. Risk Management & Trade Management

### 3.1 Hard Stops (Stop Loss)
*   **Static SL:** A fixed point-based stop loss is applied to each leg upon entry.
*   **Slippage Management:** Incorporates a configurable slippage buffer (`slippage` parameter) when calculating trigger and limit prices for SL orders.

### 3.2 Dynamic Boundary Management (Support & Resistance)
The system integrates with a `signals.csv` or YAML-based support/resistance feed.
*   **Boundary Checking:** The engine continuously monitors if the option price or underlying index price violates technical "bands".
*   **Exit Logic:** If a price crosses a support/resistance threshold or a target/SL bound, the system triggers a `MARKET` exit for the active position.

### 3.3 Re-Entry Logic
*   **Recycle Trade:** If a stop-loss is triggered, the system can be configured to re-evaluate and "Short" a new position (often at a new ATM strike) to maintain the straddle's delta-neutral profile.

## 4. Execution Workflow
1.  **Pre-Flight:** Validates current time against `program.start` and `program.stop`.
2.  **Token Discovery:** Fetches and filters the option chain from the broker (Kite API) based on the specified `base` and `expiry_offset`.
3.  **WebSocket Integration:** Establishes a real-time feed for the underlying index and specific option instruments to ensure low-latency monitoring.
4.  **Order Orchestration:** Uses the `Helper` abstraction to manage order IDs and state transitions (Open -> Complete -> Hit SL).
5.  **Shutdown:** At `program.stop`, the system cancels all pending orders and closes out all open positions via market orders.

## 5. Technical Parameters (Configurable via `settings.yml`)
*   **Quantity:** Position sizing per leg.
*   **Target:** Profit-taking threshold in points.
*   **Stop Loss:** Maximum risk per leg in points.
*   **Expiry Offset:** Target current week (0) or next week (1) expiries.
## 6. Risk Analysis: Both (Short Straddle) Strategy

The `Both` strategy (Short Straddle) is a high-probability, income-generating strategy that carries significant tail risks. As the system is automated, understanding these risks is critical for capital preservation.

### 6.1 Gamma Risk (Directional Explosion)
*   **The Risk:** Short straddles have negative Gamma. If the underlying index makes a sharp, fast move in either direction, the Delta of one leg will rapidly increase, causing exponential losses.
*   **System Mitigation:** The engine relies on `SL-M` (Stop Loss Market) orders. However, in "gap" scenarios (e.g., a 2% index gap-up at open), the SL may trigger far beyond the intended price, leading to significant slippage.

### 6.2 Vega Risk (Volatility Expansion)
*   **The Risk:** Short straddles are "Short Volatility." If the Implied Volatility (IV) of the options increases (e.g., ahead of a major news event or during a market crash), the price of both the Call and Put will rise even if the underlying price remains static.
*   **System Impact:** An IV spike can hit stop-losses on both legs simultaneously (the "double-stop" scenario), resulting in a net loss despite no significant directional move.

### 6.3 Execution & Latency Risk
*   **Slippage:** The use of `MARKET` orders for entry and `SL-M` for exit ensures execution but at the cost of price certainty. In illiquid markets or during high volatility, the difference between the intended SL and the actual fill price (slippage) can be substantial.
*   **WebSocket Dependency:** The system's monitoring loop depends on continuous data from the Kite WebSocket. A connection drop or data lag could delay the identification of an "out of bounds" condition or a stop-loss trigger.

### 6.4 Structural Risk: The "Churn" (Re-entry Risk)
*   **The Risk:** The current implementation in `Both.run()` allows for re-entering a short position after a stop-loss is hit if the price returns within "bounds."
*   **Danger:** In a "sideways-to-volatile" market (whipsaw), the system could repeatedly enter and exit trades, accumulating losses through multiple stop-loss hits and transaction costs (brokerage/STT).

### 6.5 Overnight/Gap Risk
*   **The Risk:** Since the strategy is automated for intraday (`program.start` to `program.stop`), any failure to close positions before the market close exposes the trader to overnight gaps.
*   **System Mitigation:** The `else` block in the `run()` method attempts to cancel all orders and exit all positions. If the server or script crashes right before the `stop` time, manual intervention is required.

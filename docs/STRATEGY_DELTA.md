# Strategy Specification: 'Delta' Bitcoin Monthly Straddle

## 1. Overview
The 'Delta' strategy is a positional, monthly short straddle strategy executed on **Delta Exchange India**, specifically targeting **Bitcoin (BTC)** options. Unlike the 'Both' strategy, which is intraday and index-based, 'Delta' is designed to capture theta decay over a full monthly cycle.

## 2. Key Variations from 'Both' Strategy

| Feature | 'Both' Strategy (Bank Nifty/Sensex) | 'Delta' Strategy (Bitcoin) |
| :--- | :--- | :--- |
| **Underlying** | Spot Index (NSE/BSE) | **Monthly BTC Future** (Delta Exchange) |
| **Frequency** | Intraday (Daily) | **Positional (Monthly)** |
| **Lifecycle** | 9:30 AM to 3:00 PM | **Start of Month to Expiry/Target** |
| **Persistence** | Session-based (Resets daily) | **Positional (Saves state to disk)** |
| **Exchange** | Kite/KiteExt (India) | **Delta Exchange India** |
| **Integration** | Bypass/Zerodha Bridges | **Broker-AI Bridge** |
| **Asset Class** | Equity Derivatives | **Crypto Derivatives** |

## 3. Core Mechanics (Stop and Reverse - SAR)
The 'Delta' strategy utilizes a **Stop and Reverse (SAR)** mechanism with iterative target management. All activities from the initial Short Straddle entry until the price reaches the T2 or T-2 boundaries are collectively referred to as **T1**.

*   **Initial Neutrality:** The trade begins as a Delta-Neutral Short Straddle (Short CE + Short PE).
*   **Action Zone Definition:** Upon entry, the total premium (Call + Put) is recorded to define the **T2** (LTP + Premium) and **T-2** (LTP - Premium) boundaries.
*   **The Pivot (SAR):** Hitting a stop-loss on a short leg triggers an immediate reversal into a **Long** position of the same leg.
    *   **In a Rally:** The trader becomes **Short Put + Long Call** (Synthetically Long).
    *   **In a Flush:** The trader becomes **Short Call + Long Put** (Synthetically Short).
*   **Active Leg Management (Long Side - T1):**
    *   **Same Stop:** The new Long position uses the same stop-loss distance as the original short position.
    *   **Target Achievement:** The Long position has a specific profit target.
    *   **Time To Live (TTL):** Buy trades belonging to T1 must exit before hitting their target if they exceed their predefined **Time To Live**.
    *   **Profit Zone Condition:** A TTL-based exit is ONLY triggered if the position is currently in the **profit zone** (LTP > Entry Price).
    *   **Transition on Target:** If the Long leg hits its target, the trader exits and **Shifts Strike** by selling a new **In-The-Money (ITM)** option at a further strike.
*   **Continuous SAR Cycle:** If any Long leg hits its stop-loss, it performs an SAR back into a short position.

## 4. The Action Zones: T-Series Recursion (Credit Exhaustion Points)
The strategy uses an iterative expansion of action zones to track market movement and reset credit.
*   **T1 (Entry):** The initial total premium defines the first boundaries: **T2** (Upper) and **T-2** (Lower).
*   **T-Series Evolution:** When price reaches a boundary (e.g., T2), the system executes a protocol (shifting the opposite leg) and calculates the **next** boundaries (e.g., T3 and T-3) based on the fresh premium collected.
*   **Credit Reset:** This recursive process allows the trade to follow the market move while continuously resetting the credit buffer and locking in profits from decayed legs.

### **The T_upper Protocol (Upside Action)**
When the Bitcoin Monthly Future is beyond the current **Upper Bound** (e.g., T2):
1.  **Mandatory Check:** The system ONLY acts if the **Call leg is currently Long** (SAR has been triggered).
2.  **Sell New Put:** A new Put is sold at the higher strike to collect fresh premium.
3.  **Close Initial Put:** Once the new Put is filled, the initial Put (now decayed) is closed.
4.  **No SAR for Shifted Puts:** Puts sold during a T-series shift have a **Stop Loss only**. They will never reverse into a Long position.

## 5. The Short-Side Interlock (The Binary State Machine)
To manage complexity during action zone churn, the strategy uses a strict **Short-Side Interlock**:
*   **THE RULE:** **Never sell a Put when a Call is already sold** (and vice-versa, after the initial entry).
*   **The Master Switch:** The state of one leg acts as the controller for the other:
    1.  **If Leg A = LONG:** The opposite side (Leg B) is "Active" and can be shifted to collect premium.
    2.  **If Leg A = SHORT:** The opposite side (Leg B) is "Disabled" and any existing position is closed. This prevents being "Double Short" and ensures the strategy remains in a premium-harvesting phase.

## 6. State Management and Resuming
Because the strategy is positional and spans multiple days/weeks, it implements robust state persistence:
*   **Automatic Persistence:** Every state change (reversals, tier increases, strike shifts) is immediately saved to `data/delta_state.yml`.
*   **Resumption Logic:** Upon startup, the system checks for an existing state file. If found, it reconstructs the entire operational context:
    *   Current T-Series Tier (T1, T2, T3...).
    *   Active Upper and Lower action zone boundaries.
    *   Individual leg statuses, symbols, and precise entry timestamps for TTL tracking.
*   **Network Safety:** This ensures that in case of server restarts, internet disconnects, or broker API timeouts, the system resumes exactly where it left off without re-entering initial positions.

## 7. Technical Integration
*   **Broker:** `delta-india` (Configured in `settings.yml`).
*   **Bridge:** [broker-ai](https://github.com/pannet1/broker-ai) (Replaces legacy `stock-brokers` and `omspy-brokers`).
*   **Ticker:** Uses the specialized AI-powered ticker for low-latency Bitcoin option quotes.
*   **Configuration:** Strategy parameters (Target, SL, TTL) are managed in `src/resources/settings.yml`.

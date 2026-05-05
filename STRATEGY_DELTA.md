# Strategy Specification: 'Delta' Bitcoin Monthly Straddle

## 1. Overview
The 'Delta' strategy is a positional, monthly short straddle strategy executed on **Delta Exchange India**, specifically targeting **Bitcoin (BTC)** options. Unlike the 'Both' strategy, which is intraday and index-based, 'Delta' is designed to capture theta decay over a full monthly cycle.

## 2. Key Variations from 'Both' Strategy

| Feature | 'Both' Strategy (Bank Nifty/Sensex) | 'Delta' Strategy (Bitcoin) |
| :--- | :--- | :--- |
| **Underlying** | Spot Index (NSE/BSE) | **Monthly BTC Future** (Delta Exchange) |
| **Frequency** | Intraday (Daily) | **Positional (Monthly)** |
| **Lifecycle** | 9:30 AM to 3:00 PM | **Start of Month to Expiry/Target** |
| **Constituents** | HDFC, ICICI, etc. (SR Lines used) | **None** (Bank-based SR logic removed) |
| **Exchange** | Kite/KiteExt (India) | **Delta Exchange India** |
| **Asset Class** | Equity Derivatives | **Crypto Derivatives** |

## 3. Core Mechanics (Stop and Reverse - SAR)
The 'Delta' strategy utilizes a **Stop and Reverse (SAR)** mechanism with iterative target management:

*   **Initial Neutrality:** The trade begins as a Delta-Neutral Short Straddle (Short CE + Short PE).
*   **Action Zone Definition:** Upon entry, the total premium (Call + Put) is recorded to define the **T2** (LTP + Premium) and **T-2** (LTP - Premium) boundaries.
*   **The Pivot (SAR):** Hitting a stop-loss on a short leg triggers an immediate reversal into a **Long** position of the same leg.
    *   **In a Rally:** The trader becomes **Short Put + Long Call** (Synthetically Long).
    *   **In a Flush:** The trader becomes **Short Call + Long Put** (Synthetically Short).
*   **Active Leg Management (Long Side):**
    *   **Same Stop:** The new Long position uses the same stop-loss distance as the original short position.
    *   **Target Achievement:** The Long position has a specific profit target.
    *   **Transition on Target:** If the Long leg hits its target, the trader exits and **Shifts Strike** by selling a new **In-The-Money (ITM)** option at a further strike.
*   **Continuous SAR Cycle:** If any Long leg hits its stop-loss, it performs an SAR back into a short position.

## 4. The Action Zones: T2 & T-2 (Credit Exhaustion Points)
T2 ($85,000) and T-2 ($73,000) are the levels where the initial total premium ($6,000) is fully consumed. These are "Next Action" zones used to reset the trade's credit buffer.

### **The T2 Protocol (Upside Action)**
When the Bitcoin Monthly Future is beyond **T2**:

1.  **Mandatory Check:** The system ONLY acts if the **Call leg is currently Long** (SAR has been triggered). If the Call is still Short or Flat, no action is taken at T2.
2.  **Sell New Put:** A new Put is sold at the higher strike (e.g., $85,000).
3.  **Close Initial Put:** Once the new Put is filled, the initial $79,000 Put is closed.
4.  **No SAR for T2 Puts:** These specific Puts sold at T2 have a **Stop Loss only**. They will never reverse into a Long position.

### **What the T2 Protocol achieves:**
*   **Books Put Profit:** It closes the initial Put (which is now worth very little) to lock in that decay profit.
*   **Resets the Buffer:** By selling a fresh Put at the higher strike, you collect a new chunk of premium. This "moves the floor up" and provides a new safety buffer for the trade as it continues to follow the rally with the Long Call.

## 5. Case Study: Bitcoin Price Simulation
### **Phase 1: Entry**
*   **BTC Monthly Future:** $79,000. **Short $79,000 Straddle**.
*   **Total Premium:** $6,000.
*   **Action Zones (T2/T-2):** $85,000 / $73,000.

### **Phase 2: SAR & Target Shift**
*   **BTC Rallies to $82,000:** Short Call hits SL. **SAR to Long 79k Call**.
*   **BTC Hits Target at $84,000:** Exit Long 79k Call. **Sell ITM 84k Call**.

### **Phase 3: T2 Put-Shift**
*   **BTC Hits $85,000 (T2):** 
    *   Check: Is Call Long? (If the 84k Call SAR'd back to Long, then Yes).
    *   Action: **Sell 85k Put, Close 79k Put**.

## 6. The Short-Side Interlock (Solving the "Memory Problem")
To solve the difficulty of "remembering" where to re-enter Puts during a T2 churn, the strategy uses a strict **Short-Side Interlock**:

*   **THE RULE:** **Never sell a Put when a Call is already sold** (and vice-versa, after the initial entry).
*   **The Master Switch:** The state of the **Call leg** acts as the controller for the Put side:
    1.  **Call = LONG:** The Put side is "Active." You can sell/re-sell Puts at T2 to collect premium because your upside is protected by the Long Call.
    2.  **Call = SHORT:** (e.g., after shifting to an ITM Short Call). The Put side is "Disabled." You cannot sell a Put. This prevents you from being "Double Short" and removes the need to track Put levels when the market is in a premium-harvesting phase.

### **Strategic Advantage:**
This rule turns the strategy into a simple **Binary State Machine**. You never have to "remember" Put levels—you only have to look at whether your Call is currently Long or Short.

### Bank Nifty Short Straddle

#### Step-by-Step Strategy:

1. **Initial Entry:**
   - Take 1 lot (configurable quantity) of short straddle on Bank Nifty at a specified entry time (configurable).

2. **Stop Loss Setup:**
   - Set a stop loss (SL) for 2 lots (configurable quantity) at 60 points on each side (Call and Put).
     - The 60 points SL is per leg and should be configurable.
     - If the SL is hit on either side, you will have 1 lot of a buy position on the same side and 1 lot of a sell position on the opposite side.

3. **Monitoring Support and Resistance Levels:**
   - Support and resistance levels for Bank Nifty and other monitored stocks (HDFC, ICICI, SBI, AXIS) are predefined and read-only at the start.
   - Note down the current price of these stocks when the stop loss is hit, and this will be between the predefined support and resistance levels.

4. **Exit Condition Based on Support and Resistance:**
   - Exit the buy Call Position (CE) if:
     - The current price of Bank Nifty crosses above the predefined resistance level or crosses below the predefined support level.
     - The price of the monitored stock crosses above its respective resistance level or drops below its respective support level.
   - Exit the buy Put Position (PE) if:
     - The current price of Bank Nifty drops below the predefined support level or crosses above the predefined resistance level.
     - The price of the monitored stock drops below its respective support level or crosses above its respective resistance level.
   - If any of these conditions are met, exit the respective position and proceed to the next step.

5. **Sell Another Option (CE or PE) with ATM Strike:**
   - After the SL is hit and positions are adjusted:
     - **For Call Position (CE):** Sell another Call option (CE) with an ATM (At The Money) strike price.
       - Place a new SL for double the initial quantity (2 lots, configurable) at 60 points.
     - **For Put Position (PE):** Sell another Put option (PE) with an ATM (At The Money) strike price.
       - Place a new SL for double the initial quantity (2 lots, configurable) at 60 points.

### Example Workflow:

1. **Initial Entry:**
   - Enter 1 lot (configurable quantity) of short straddle on Bank Nifty at the specified entry time.

2. **Stop Loss Setup:**
   - Set SL for 2 lots (configurable quantity) at 60 points (configurable) for both Call and Put.
   - If the SL is hit on either side, adjust positions accordingly and note down the current prices of monitored stocks.

3. **Monitor SR Levels:**
   - When the current price of Bank Nifty or monitored stocks crosses above the predefined resistance level or drops below the predefined support level, exit the buy Call or Put position accordingly.

4. **Sell Another Option (CE or PE) with ATM Strike:**
   - After the SL is hit and positions are adjusted:
     - **For Call Position (CE):** Sell another Call option (CE) with an ATM strike price and set a new SL for double the initial quantity at 60 points.
     - **For Put Position (PE):** Sell another Put option (PE) with an ATM strike price and set a new SL for double the initial quantity at 60 points.

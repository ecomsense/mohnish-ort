### Bank Nifty Short Straddle

#### Step-by-Step Strategy:

1. **Initial Entry:**
   - Take 1 lot (configurable quantity) of short straddle on Bank Nifty at 9:30 AM.
     - The entry time should be configurable.

2. **Stop Loss Setup:**
   - Set a stop loss (SL) for 2 lots (configurable quantity) at 60 points on each side (Call and Put).
     - The 60 points SL is per leg and should be configurable.
     - If the SL is hit on either side, you will have 1 lot of a buy position on the same side and 1 lot of a sell position on the opposite side.

3. **Post Stop Loss Adjustment:**
   - If the SL is hit on either side (Call or Put), adjust positions as follows:
     - Example: If the Call SL is hit, you will have 1 lot of bought Call and 1 lot of sold Put.
   - Place a new SL for double the initial quantity (2 lots, configurable) at 60 points on the newly bought position only.
     - The 60 points SL is calculated from the new entry point of the remaining bought position.
   - If a new sell position is initiated after the SL hits on the buy side, create a new SL at 60 points (configurable) for this sell position.

4. **Monitoring Support and Resistance Levels:**
   - Support and resistance levels for Bank Nifty, HDFC, ICICI, SBI, and AXIS Bank are predefined in a `settings.yml` file, initialized at the start.
   - When the SL is hit and positions are adjusted (step 3), note down the current price of Bank Nifty and other monitored stocks.

5. **Exit Condition Based on Support and Resistance Breach:**
   - If the SL is hit and the current price of the stocks breaches a predefined resistance level (for Call) or support level (for Put), exit all positions.
     - For **Call Position**: If the current price is above the predefined resistance level, exit all positions.
     - For **Put Position**: If the current price is below the predefined support level, exit all positions.
   - After exiting all positions, prepare for re-entry based on the initial entry conditions.

6. **Re-entry Configuration:**
   - Re-enter the short straddle from the beginning, following steps 1 to 4.
   - The number of re-entries should be configurable. Define how many times the strategy should attempt to re-enter after an exit.

### Example Workflow:

1. **Initial Entry:**
   - Enter 1 lot (configurable quantity) of short straddle on Bank Nifty at 9:30 AM (configurable).

2. **Stop Loss Setup:**
   - Set SL for 2 lots (configurable quantity) at 60 points (configurable) for both Call and Put.
   - If the SL is hit on either side, you will have 1 lot of a buy position on the same side and 1 lot of a sell position on the opposite side.

3. **SL Hit:**
   - Suppose the Call SL is hit:
     - You now have 1 lot of bought Call and 1 lot of sold Put.
   - Place a new SL for double the initial quantity (2 lots, configurable) at 60 points (configurable) on the bought Call position.

4. **Monitor SR Levels:**
   - When the current price of Bank Nifty and other stocks breaches the predefined resistance level (for Call) or support level (for Put), exit all positions.
   - After exiting, prepare for re-entry based on the initial entry conditions.

5. **Re-Entry:**
   - Re-enter the short straddle from the beginning, following steps 1 to 4.
   - Repeat the re-entry process according to the configured number of re-entries.

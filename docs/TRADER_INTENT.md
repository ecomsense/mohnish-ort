# Trader Intent: Coinshort Strategy

## Core Bet
The trader believes **BTC will be range-bound** (low volatility). They sell a short straddle (ATM call + put) to collect premium (theta decay). Profit when price stays within `[entry ± premium]`.

## T1 — Rolling SAR (Mean Reversion)
When the market moves against one leg:

1. **SHORT → SL hit → flip to LONG** (now riding the move, not fighting it)
2. **LONG → SL hit → flip back to SHORT** (re-enter short at new ATM strike)
3. **LONG → target hit → roll** (modify SL to market, sell new ATM short of same type, lock profit on long)
4. **LONG → TTL expired + in profit → roll** (same as target hit)

**Trader expects:** *"When challenged, don't die — join the move, profit from a reversal, or roll."*

## T2 — First Breach (Trend Starts)
The market breaches a bound **and** the stretched leg is already LONG:

1. **Upper breach + CE is LONG** → sell a **put** on the far side (collect premium from the side the market left behind)
2. **Lower breach + PE is LONG** → sell a **call** on the far side
3. **Expand bounds** outward by new premium

**Trader expects:** *"Market is moving — sell premium on the side it's leaving. Widen the fence."*

## T3 — Second Breach (Close Original Opposite Leg)
First time `_close_satellite(tier-2=1)` fires. Special case: closes `self.pe` or `self.ce` — the **original T1 opposite-side leg**:

1. **Close the original T1 opposite leg** — the one left behind when the market first breached. Now deep OTM, fully decayed, premium already collected. Close it for pennies.
2. **Sell a new satellite** on the opposite side at T3.
3. **Expand bounds** outward by new premium.

**Trader expects:** *"Trend is real. Bank the decaying T1 ghost. Sell fresh premium on the side the market leaves. Widen again."*

## T4+ — Further Breaches (Rolling Satellite Pattern)
Each further breach repeats the T3 pattern, but closes from the `_satellites[]` list:

1. **Close satellite at tier-2** — the satellite sold two tiers ago. Deep OTM, cheap to close.
2. **Sell a new satellite** on the opposite side at the new tier.
3. **Expand bounds** outward by new premium.

**Trader expects:** *"Same pattern: close the oldest decaying ghost. Sell fresh premium on the departing side. Keep widening."*

## Ideal Scenario
Range-bound day → theta decays both legs → straddle expires worthless → max profit = full premium collected.

## Why It Fails (trader's fear)
- **Gap move** past all bounds (SLs on all legs trigger → max loss)
- **Whiplash** (LONG→SHORT→LONG repeatedly → commissions + slippage eat premium)
- **Illegible satellite management** (wrong leg closed, old orders dangling, positions doubled)

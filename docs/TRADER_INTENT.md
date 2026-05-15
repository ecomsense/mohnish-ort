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

## T2 — Action Zones (Trend Adaptation)
When the market **keeps trending** (breaches bound + stretched leg is already LONG):

1. **Upper breach + CE is LONG** → sell a **put** on the far side (collect premium from the side the market left behind)
2. **Lower breach + PE is LONG** → sell a **call** on the far side
3. **Close satellite at tier-2** — the opposite-side leg from T1 (e.g. sell PE at T2 upper breach, close original T1 PE at T3). Now deep OTM since the market has trended away — theta-decayed, cheap to close, premium already banked.
4. **Expand bounds** outward by new premium

**Trader expects:** *"If the market trends, sell premium on the side it's abandoning. Two breaches later, collect the decaying OTM ghost for pennies. Widen the fence."*

## Ideal Scenario
Range-bound day → theta decays both legs → straddle expires worthless → max profit = full premium collected.

## Why It Fails (trader's fear)
- **Gap move** past all bounds (SLs on all legs trigger → max loss)
- **Whiplash** (LONG→SHORT→LONG repeatedly → commissions + slippage eat premium)
- **Illegible satellite management** (wrong leg closed, old orders dangling, positions doubled)

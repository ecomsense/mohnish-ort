# Trader Intent: Coinshort Strategy

## Naming
- **Stretched leg** = the option (CE/PE) that flipped LONG after SL hit
- **Counter-leg** = the opposite option type. CE ↔ PE
- **T2, T3, T4** = upper breaches (market rallies from T1 entry)
- **T-2, T-3, T-4** = lower breaches (market drops from T1 entry)

## Core Bet
The trader believes **BTC will be range-bound** (low volatility). They sell a short straddle (ATM call + put) to collect premium (theta decay). Profit when price stays within `[entry ± premium]`.

## T1 — Rolling SAR (Mean Reversion)
Each leg independently follows this cycle:

1. **SHORT → SL hit** → flip to LONG (join the move, ride the reversal)
2. **LONG → target hit** → roll: exit long (modify SL→market), sell new ATM short of same type
3. **LONG → TTL exceeded + in profit** → roll: same as target hit
4. **LONG → SL hit** → flip to SHORT (mean reversion: sell new ATM short of same type)

**Trader expects:** *"When challenged, don't die — join the move, profit from a reversal, or roll."*

## T2 (upper) / T-2 (lower) — First Breach
The market breaches a bound **and** the stretched leg is already LONG:

| Condition | Action |
|-----------|--------|
| T2: market rallies, CE is stretched | Sell PE counter-leg satellite |
| T-2: market drops, PE is stretched | Sell CE counter-leg satellite |

Then: expand bounds outward by new premium.

**Trader expects:** *"Trend detected — sell premium on the counter-leg (the side the market left behind). Widen the fence."*

## T3 (upper) / T-3 (lower) — Second Same-Direction Breach
First time `_close_satellite(tier-2=1)` fires. Closes the original T1 counter-leg:

| Sequence | Close this |
|----------|------------|
| T3: second upper breach | Close original T1 PE (counter-leg to stretched CE). Now deep OTM, fully decayed. |
| T-3: second lower breach | Close original T1 CE (counter-leg to stretched PE). Now deep OTM, fully decayed. |

Then: sell new counter-leg satellite at current tier, expand bounds.

**Trader expects:** *"Trend is real. Bank the decaying T1 counter-leg ghost. Sell fresh premium on the counter-leg. Widen again."*

## T4+ (upper) / T-4+ (lower) — Further Same-Direction Breaches
Same pattern as T3/T-3, but closes from `_satellites[]` list instead of the original T1 leg:

| Sequence | Close this |
|----------|------------|
| T4 | Close T2 PE satellite (tier-2). Deep OTM. |
| T-4 | Close T-2 CE satellite (tier-2). Deep OTM. |

Then: sell new counter-leg satellite, expand bounds.

**Trader expects:** *"Same pattern: close the oldest decaying ghost from the satellite list. Sell fresh premium on the counter-leg. Keep widening."*

## Ideal Scenario
Range-bound day → theta decays both legs → straddle expires worthless → max profit = full premium collected.

## Why It Fails (trader's fear)
- **Gap move** past all bounds (SLs on all legs trigger → max loss)
- **Whiplash** (LONG→SHORT→LONG repeatedly → commissions + slippage eat premium)
- **Illegible satellite management** (wrong counter-leg closed, old orders dangling, positions doubled)

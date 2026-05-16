# Trader Intent: Coinshort Strategy

## Naming
- **Stretched leg** = the option (CE/PE) that flipped LONG after SL hit
- **Counter-leg** = the opposite option type. CE ↔ PE
- **T2, T3, T4** = upper breaches (market rallies from T1 entry)
- **T-2, T-3, T-4** = lower breaches (market drops from T1 entry)

## Core Bet
The trader believes **BTC will be range-bound** (low volatility). Sell ATM straddle (call + put) to collect premium (theta decay). Profit when price stays within `[entry ± premium]`.

## Order Discipline — Never Cancel
Orders are **never cancelled**. They either stay until triggered, or get modified to MARKET for immediate exit.

| Scenario | What happens |
|----------|-------------|
| SL not hit | Stays in place |
| SL hit | Fills naturally → state machine processes the transition |
| Need to exit (target/TTL/satellite close) | **Modify existing SL to MARKET.** No cancels, no races. |

## T1 — Rolling SAR (Mean Reversion)

| Current | Trigger | Next | Action |
|---------|---------|------|--------|
| SHORT | SL hit | LONG | BUY MARKET to close short + open long (qty=1 each), place SELL SL |
| LONG | Target hit | SHORT | Modify SELL SL→MARKET, `enter_short` at new ATM strike |
| LONG | TTL + profit | SHORT | Same as target |
| LONG | SL hit | SHORT | `enter_short` at new ATM strike |
| SHIFTED | SL hit | FLAT | Modify BUY SL→MARKET |

**Trader expects:** *"When challenged, join the move. Profit from reversal or roll."*

## T2 / T-2 — First Breach
Bound breached **and** stretched leg is LONG → sell counter-leg satellite, expand bounds.

| Breach | Condition | Sell |
|--------|-----------|------|
| Upper | price ≥ upper, CE is LONG | PE counter-leg |
| Lower | price ≤ lower, PE is LONG | CE counter-leg |

**Trader expects:** *"Sell premium on the side the market left. Widen the fence."*

## T3 / T-3 — Second Breach
`_close_satellite(tier-2=1)` fires. Modifies original T1 counter-leg SL→MARKET (deep OTM, fully decayed). Sells new counter-leg satellite. Expands bounds.

## T4+ / T-4+ — Further Breaches
Same as T3, but closes tier-2 satellite from `_satellites[]` list instead of original T1 leg.

## Why It Fails
- **Trend** past all bounds → SL cascade → max loss
- **Whiplash** → frequent SAR cycles → friction eats premium
- **Wrong satellite closed** → direction-ambiguous close (fixed: `counter_leg` param)

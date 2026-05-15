# Intent vs Code: Gap Analysis

## T1 — Rolling SAR

| Trader Intent | Code Location | Status |
|---|---|---|
| SHORT → SL hit → flip to LONG | `order_manager.py:112-132` | ✅ Matches |
| LONG → SL hit → flip back to SHORT | `order_manager.py:172-191` | ✅ Matches |
| LONG → target hit → roll | `order_manager.py:134-151` | ✅ Matches (but B3) |
| LONG → TTL exceeded + in profit → roll | `order_manager.py:152-171` | ✅ Matches (but B3) |

## T2 — First Breach

| Trader Intent | Code Location | Status |
|---|---|---|
| Upper breach + CE LONG → sell PE | `coinshort.py:202-227` | ✅ |
| Lower breach + PE LONG → sell CE | `coinshort.py:229-254` | ✅ |
| Expand bounds | `coinshort.py:224-225, 251-252` | ✅ |
| Skip if satellite exists at this tier | `coinshort.py:203, 230` | ✅ |

## T3 — Second Breach

| Trader Intent | Code Location | Status |
|---|---|---|
| Close original T1 opposite leg | `_close_satellite(1)` → `coinshort.py:189-193` | ❌ **B1: hardcodes `self.pe`** — at T3 lower breach (market dropped twice), should close `self.ce` (original call, now deep OTM). Code always closes `self.pe`. |
| Sell new satellite at new tier | `coinshort.py:207/234` | ✅ |
| Expand bounds | `coinshort.py:224-225, 251-252` | ✅ |

## T4+ — Further Breaches

| Trader Intent | Code Location | Status |
|---|---|---|
| Close satellite at tier-2 | `_close_satellite(tier>=2)` → `coinshort.py:195-200` | ✅ |
| Sell new satellite at new tier | `coinshort.py:207/234` | ✅ |
| Expand bounds | `coinshort.py:224-225, 251-252` | ✅ |

---

## Gaps Between Intent and Code

### Critical

1. **B1: `_close_satellite(tier=1)` always closes PE** (`coinshort.py:189`)
   - Upper breach T3 → PE is correct (market rallied, PE is OTM)
   - Lower breach T3 → should close CE, not PE → wrong leg closed
   - Root cause: `_close_satellite` has no awareness of breach direction

2. **B2: Entry order IDs not persisted** (`coinshort.py:31-32` not in `save_state`)
   - Crash during straddle entry → on restart, `_entry_ce_id` / `_entry_pe_id` are None → re-enters straddle → doubled position
   - Trader intent assumes one clean entry

3. **B3: SL modify races with SL trigger** (`order_manager.py:137, 157`)
   - `order_modify(order_type="MARKET")` on the existing SL order races with the SL trigger
   - If SL fills first → we're flat, then modify fails or acts on a filled order
   - If modify wins → SL order becomes MARKET, fills at bad price
   - Needs: cancel-first, then place fresh MARKET exit

### Moderate

4. **Satellite short fill never verified** (`coinshort.py:207-222, 234-249`)
   - `enter_short` places SELL MARKET + BUY SL. Satellites only track `buy_id`.
   - If SELL MARKET never fills → orphaned BUY SL with no position
   - Trader intent assumes satellite is active and collecting premium

5. **No WS reconnect for option tokens** (`engine.py:16-17`)
   - On reconnect, only underlying token is re-subscribed
   - OM tracks `_subscribed` set but it's never used during reconnection
   - LTP reads after reconnect return 0.0 → wrong decisions

6. **save_state() on every tick** (`coinshort.py:182`)
   - Disk I/O on every ~100ms tick
   - Behavioral gap: wastes I/O, but no correctness issue

### Doc-Code Mismatches

7. **T3 "close opposite leg" is direction-ambiguous**
   - Doc correctly says "close the original T1 opposite leg"
   - Code can only close PE — works for upper breach, fails for lower breach
   - Either: fix code to dispatch on direction, or update doc to note limitation

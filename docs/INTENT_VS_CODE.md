# Intent vs Code: Gap Analysis

## T1 — Rolling SAR

| Trader Intent | Code Location | Status |
|---|---|---|
| SHORT → SL hit → flip to LONG | `order_manager.py:112-132` | ✅ |
| LONG → SL hit → flip back to SHORT | `order_manager.py:172-191` | ✅ |
| LONG → target hit → roll (modify SL→MARKET) | `order_manager.py:135-158` | ✅ |
| LONG → TTL exceeded + profit → roll | `order_manager.py:159-185` | ✅ |

## T2 / T-2 — First Breach

| Trader Intent | Code Location | Status |
|---|---|---|
| Upper breach + CE LONG → sell PE counter-leg | `coinshort.py:207-232` | ✅ |
| Lower breach + PE LONG → sell CE counter-leg | `coinshort.py:234-259` | ✅ |
| Expand bounds | `coinshort.py:228-231, 255-258` | ✅ |
| Skip if satellite exists at this tier | `coinshort.py:208, 235` | ✅ |

## T3 / T-3 — Second Breach

| Trader Intent | Code Location | Status |
|---|---|---|
| Modify T1 counter-leg SL → MARKET (exit) | `_close_satellite(1, counter_leg)` → `coinshort.py:192-199` | ✅ **Fixed B1** |
| Sell new counter-leg satellite | `coinshort.py:212-227, 239-254` | ✅ |
| Expand bounds | `coinshort.py:228-231, 255-258` | ✅ |

## T4+ / T-4+ — Further Breaches

| Trader Intent | Code Location | Status |
|---|---|---|
| Modify tier-2 satellite SL → MARKET | `_close_satellite(tier>=2)` → `coinshort.py:200-205` | ✅ |
| Sell new counter-leg satellite | `coinshort.py:212-227, 239-254` | ✅ |
| Expand bounds | `coinshort.py:228-231, 255-258` | ✅ |

---

## Order Discipline — Never Cancel

| Principle | Code Evidence |
|---|---|
| No order_cancel anywhere in management path | All exits use `order_modify(..., order_type="MARKET")` to trigger immediate fill on existing SL |
| SLs stay in place until they fire or get modified | `order_manager.py:137, 157` — modify to MARKET |
| Satellite close uses same modify-to-MARKET pattern | `coinshort.py:194, 202` — `order_modify` on the SL |

## Historical Bug Status

| Bug | Status | Fix |
|---|---|---|
| **B1** — `_close_satellite(1)` hardcoded PE | **Fixed** | Added `counter_leg` param. T3 upper closes PE, T-3 lower closes CE. |
| **B2** — Entry order IDs not persisted | **Fixed** | `_entry_ce_id` / `_entry_pe_id` saved/loaded in state. |
| **B3** — SL modify races trigger | **Not a bug** | `order_modify` is correct. When target/TTL hit, modifying the SL to MARKET triggers immediate fill. Both outcomes (modify wins / SL triggers) achieve the same exit. No cancel needed. |

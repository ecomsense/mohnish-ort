# Intent vs Code: Gap Analysis

## Fixed Bugs

| Bug | Description | Fix |
|-----|-------------|-----|
| B1 | `_close_satellite(1)` always closed PE | Added `counter_leg` param; T3 upper→closes PE, T-3 lower→closes CE |
| B2 | Entry order IDs not persisted | Added `_entry_ce_id`/`_entry_pe_id` to `save_state()`/`load_state()` |
| B3 | `order_modify` races with SL | Not a bug — `order_modify` is the correct pattern per no-cancel discipline |
| SL qty | SL was `qty * 2` instead of `qty` | Changed to `qty=1`, added explicit MARKET BUY for SAR long entry |

## T1 — Rolling SAR

| Intent | Code | Status |
|--------|------|--------|
| SHORT→SL→LONG | `order_manager.py:112-140` | ✅ qty=1, explicit enter_long |
| LONG→target→roll | `order_manager.py:142-159` | ✅ tag="target_exit" |
| LONG→TTL→roll | `order_manager.py:161-186` | ✅ tag="ttl_exit" |
| LONG→SL→SHORT | `order_manager.py:187-206` | ✅ |

## T2 / T-2 — First Breach

| Intent | Code | Status |
|--------|------|--------|
| Upper breach + CE LONG → sell PE | `coinshort.py:218-243` | ✅ |
| Lower breach + PE LONG → sell CE | `coinshort.py:245-270` | ✅ |
| Expand bounds | `coinshort.py:240-242, 256-258` | ✅ bounds = premium/2 |

## T3 / T-3 — Second Breach

| Intent | Code | Status |
|--------|------|--------|
| Modify T1 counter-leg SL→MARKET | `_close_satellite(1, counter_leg)` → `coinshort.py:205-212` | ✅ dispatches on direction |
| Sell new counter-leg satellite | `coinshort.py:222-243, 249-270` | ✅ |
| Expand bounds | `coinshort.py:240-242, 256-258` | ✅ |

## T4+ / T-4+ — Further Breaches

| Intent | Code | Status |
|--------|------|--------|
| Modify tier-2 satellite SL→MARKET | `_close_satellite(tier>=2)` → `coinshort.py:213-218` | ✅ |
| Sell new satellite, expand bounds | `coinshort.py:222-258` | ✅ |

## Order Discipline

| Rule | Evidence |
|------|----------|
| Never cancel | No `order_cancel` in any management path |
| Exit via modify to MARKET | All exits use `order_modify(order_type="MARKET")` |
| Satellite close uses modify | `_close_satellite`: `order_modify` on the SL |

## Backtest Validation

| Test | Result |
|------|--------|
| April BS backtest (backtest.py) | Deprecated — use live backtest only |
| May real-price backtest (1h) | Total P&L +18950 per BTC |
| May real-price backtest (1m) | Total P&L +5667 per BTC |
| 33 unit tests | ✅ Pass |

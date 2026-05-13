# RULES: State Transitions

## T1 (per-leg state machine)

| Current | Trigger | Next | Intent |
|---------|---------|------|--------|
| SHORT | SL hit | LONG | ACTIVATE_SAR |
| LONG | target hit | SHIFTED | SHIFT_STRIKE |
| LONG | SL hit | SHORT | ENTER_SHORT_ATM |
| LONG | TTL exceeded + in profit | FLAT | EXIT_POSITION |
| SHIFTED | SL hit | FLAT | EXIT_POSITION |

## T2 (cross-leg, underlying-driven)

| Condition | Action | Intent |
|-----------|--------|--------|
| `underlying >= upper_bound AND call.state == LONG` | Shift put up | ENTER_SHORT_ATM_PE |
| `underlying <= lower_bound AND put.state == LONG` | Shift call down | ENTER_SHORT_ATM_CE |

## Interlock

Golden rule: never both legs SHORT after initial entry.

| call.state | put.state | allowed |
|------------|-----------|---------|
| SHORT | SHORT | None (initial only) |
| LONG | SHORT | Put can shift (T2) |
| SHORT | LONG | Call can shift (T2) |
| LONG | LONG | Both active independently |
| SHIFTED | * | Opposite must be FLAT or LONG |

# DESIGN: Data Structures & Interfaces

## Enums

```python
class LegState(Enum):
    FLAT = auto()
    SHORT = auto()
    LONG = auto()
    SHIFTED = auto()  # short after strike shift, no SAR

class IntentType(Enum):
    ENTER_SHORT_ATM_CE = "enter_short_atm_ce"
    ENTER_SHORT_ATM_PE = "enter_short_atm_pe"
    EXIT_POSITION = "exit"
    SHIFT_STRIKE = "shift_strike"
    ACTIVATE_SAR = "activate_sar"
    NONE = "none"
```

## Dataclasses (target — not yet implemented)

```python
@dataclass
class Intent:
    intent_type: IntentType
    leg: str        # "CE" | "PE"
    reason: str     # "sl_hit" | "target_hit" | "ttl_exceeded" | "t2_trigger"

@dataclass
class ExecutionResult:
    short_id: str
    sl_id: str
    fill_price: float
    strike: int
```

## Persistent State (JSON — coinshort_state.json)

```json
{
  "tier": 2,
  "upper_bound": 52000.0,
  "lower_bound": 48000.0,
  "current_premium": 1500.0,
  "ce": {
    "status": 2,
    "tradingsymbol": "BTC-28MAR25-50000-CE",
    "instrument_token": 1002,
    "entry_time": "2026-05-06T10:30:00",
    "buy_params": {"price": 150.0},
    "short_params": {"last_price": 150.0},
    "bounds": [[[100.0, 250.0]], [150.0]]
  },
  "pe": {
    "status": 3,
    "tradingsymbol": "BTC-28MAR25-50000-PE",
    "instrument_token": 1003,
    "entry_time": "2026-05-06T11:15:00",
    "buy_params": {"price": 180.0},
    "short_params": {"last_price": 180.0},
    "bounds": [[[130.0, 280.0]], [180.0]]
  }
}
```

*Note: `status` values are `LegState.value`: FLAT=1, SHORT=2, LONG=3, SHIFTED=4*

## Volatile State (NOT persisted)

| Field | Source |
|-------|--------|
| order_id (buy_id, short_id) | Query broker orders |
| instrument_token | Rebuild from strike |
| quotes | Live WS feed |
| underlying_price | Live WS feed |

## Interfaces

```python
class Coinshort:
    def __init__(self, config: dict, symbols: OptionSymbol, api: RestApi) -> None
    def tick(self, ws: Wsocket, books: Books) -> None
    def cleanup(self, books: Books) -> None

class OrderManager:   # target — not yet implemented
    def execute(self, intent: Intent, underlying_price: float) -> ExecutionResult

class Books:
    @property
    def positions(self) -> List[Dict]
    @property
    def orders(self) -> List[Dict]
    def is_complete(self, order_id: str) -> bool

class Wsocket:
    @property
    def ltp(self) -> dict[str, float]
    def subscribe(self, tokens: list[str]) -> None
    def connect(self, threaded: bool = True) -> None
```

## State Transitions

### T1 (per-leg)

| Current | Trigger | Next | Intent |
|---------|---------|------|--------|
| SHORT | SL hit | LONG | ACTIVATE_SAR |
| LONG | target hit | SHIFTED | SHIFT_STRIKE |
| LONG | SL hit | SHORT | ENTER_SHORT_ATM |
| LONG | TTL exceeded + in profit | FLAT | EXIT_POSITION |
| SHIFTED | SL hit | FLAT | EXIT_POSITION |

### T2 (cross-leg, underlying-driven)

| Condition | Action | Intent |
|-----------|--------|--------|
| `underlying >= upper_bound AND call.state == LONG` | Shift put up | ENTER_SHORT_ATM_PE |
| `underlying <= lower_bound AND put.state == LONG` | Shift call down | ENTER_SHORT_ATM_CE |

### Interlock

Golden rule: never both legs SHORT after initial entry.

| call.state | put.state | allowed |
|------------|-----------|---------|
| SHORT | SHORT | None (initial only) |
| LONG | SHORT | Put can shift (T2) |
| SHORT | LONG | Call can shift (T2) |
| LONG | LONG | Both active independently |
| SHIFTED | * | Opposite must be FLAT or LONG |

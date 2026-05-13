# DESIGN: Data Structures & Interfaces

## Enums

```python
class LegState(Enum):
    FLAT = 0
    SHORT = -1
    LONG = 1
    SHIFTED = 2  # short after strike shift, no SAR

class IntentType(Enum):
    ENTER_SHORT_ATM_CE = "enter_short_atm_ce"
    ENTER_SHORT_ATM_PE = "enter_short_atm_pe"
    EXIT_POSITION = "exit"
    SHIFT_STRIKE = "shift_strike"
    ACTIVATE_SAR = "activate_sar"
    NONE = "none"
```

## Dataclasses

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

## Persistent State (JSON)

```json
{
  "tier": 2,
  "upper_bound": 52000.0,
  "lower_bound": 48000.0,
  "call_strike": 50000,
  "put_strike": 50000,
  "call_state": 1,
  "put_state": -1,
  "call_entry_price": 150.0,
  "put_entry_price": 180.0,
  "call_entry_time": "2026-05-06T10:30:00",
  "put_entry_time": "2026-05-06T11:15:00"
}
```

## Volatile State (NOT persisted)

| Field | Source |
|-------|--------|
| order_id (buy_id, short_id) | Query broker orders |
| instrument_token | Rebuild from strike |
| quotes | Live WS feed |
| underlying_price | Live WS feed |

## Interfaces

```python
class Delta:
    def tick(self, ws: Wserver, books: Books) -> None

class OrderManager:
    def execute(self, intent: Intent, underlying_price: float) -> ExecutionResult

class Books:
    @property
    def positions(self) -> List[Dict]
    @property
    def orders(self) -> List[Dict]
    def is_order_complete(self, order_id: str) -> bool

class Wserver:
    def ltp(self, tokens: List[str] | None) -> List[Dict]
    def subscribe(self, tokens: List[int]) -> None
```

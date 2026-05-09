## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      STRATEGY LAYER (Pure Logic)                │
│  Input: Underlying Price + Position States                      │
│  Output: Intent Hints (e.g., "enter_short_atm_put")             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORDER MANAGER LAYER                          │
│  Input: Intent Hints                                            │
│  Responsibilities:                                              │
│    - Resolve instrument (ATM strike lookup)                     │
│    - Subscribe + fetch quote on-demand                          │
│    - Place orders (with SL, Target, Quantity)                   │
│    - SYNC ONLY: Delta Exchange India does NOT support async     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STATE PERSISTENCE                          │
│  Persistent: Tier, Bounds, Leg States, Entry Times, Strikes     │
│  Volatile: Order IDs, Instrument Tokens, Quotes                 │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Core Data Structures

### 2.1 Minimal State (What Actually Matters)

**Persistent State (save to YAML):**

| Field | Type | Why Persist? |
|-------|------|--------------|
| `tier` | int | T-series progression (T1, T2, T3...) |
| `upper_bound` | float | Action zone boundary |
| `lower_bound` | float | Action zone boundary |
| `call_strike` | int | Rebuild symbol on restart |
| `put_strike` | int | Rebuild symbol on restart |
| `call_state` | enum | FLAT/SHORT/LONG/SHIFTED |
| `put_state` | enum | FLAT/SHORT/LONG/SHIFTED |
| `call_entry_price` | float | TTL profit check |
| `put_entry_price` | float | TTL profit check |
| `call_entry_time` | datetime | TTL expiration check |
| `put_entry_time` | datetime | TTL expiration check |

**Volatile State (rebuild on restart):**

| Field | Type | Why NOT Persist? |
|-------|------|------------------|
| `order_id` (buy_id, short_id) | str | Query broker for open orders |
| `instrument_token` | str | Rebuild from strike + symbol logic |
| `quotes` | dict | Live market data |
| `underlying_price` | float | Live market data |

### 2.2 Leg State Enum

```python
class LegState(Enum):
    FLAT = 0          # No position
    SHORT = -1        # Short option (premium collection)
    LONG = 1          # Long option (SAR triggered, directional)
    SHIFTED = 2       # Short after strike shift (no SAR, premium only)
```

### 2.3 Intent Hints

```python
class IntentType(Enum):
    ENTER_SHORT_ATM_CE = "enter_short_atm_ce"
    ENTER_SHORT_ATM_PE = "enter_short_atm_pe"
    EXIT_POSITION = "exit"
    ACTIVATE_SAR = "activate_sar"      # SL already placed
    SHIFT_STRIKE = "shift_strike"      # Exit current, sell ITM
    NONE = "none"

@dataclass
class Intent:
    intent_type: IntentType
    option_type: str          # "CE" or "PE"
    reason: str               # "sl_hit", "target_hit", "ttl_exceeded", "t2_trigger"
```

## 3. Universal Rules Engine

### 3.0 Async Order Support

**Delta Exchange India does NOT support async orders.**

The `broker-ai` library (and underlying `stock_brokers.bypass`) uses synchronous `order_place()` calls:

```python
# integrations/api.py:69
def enter(self, kwargs):
    return self.api().order_place(**params)  # SYNC call, blocks until response
```

**Implications:**
- Multi-leg entries (CE + PE) execute **sequentially**, not in parallel
- Slippage risk between leg 1 and leg 2
- No `asyncio` or threading in current implementation

**Future Enhancement:** Wrap `order_place` in `asyncio.to_thread()` for concurrent execution if slippage becomes problematic.

### 3.1 T1 Rules (Simple Straddle Management)

**Entry:** Short ATM CE + Short ATM PE

**Per-Leg State Machine:**

| Current State | Trigger | Next State | Intent |
|--------------|---------|------------|--------|
| SHORT | SL Hit | LONG | `ACTIVATE_SAR` |
| LONG | Target Hit | SHIFTED | `SHIFT_STRIKE` (sell ITM) |
| LONG | SL Hit | SHORT | `ENTER_SHORT_ATM` |
| LONG | TTL Exceeded + In Profit | FLAT | `EXIT_POSITION` |
| SHIFTED | SL Hit | FLAT | `EXIT_POSITION` (no SAR) |

### 3.2 T2 Trigger Rules (Cross-Leg Protocol)

**T2 Trigger Condition:**
```python
if underlying_price >= upper_bound AND call_leg.state == LONG:
    # Execute T_upper_protocol
    intent = Intent(ENTER_SHORT_ATM_PE, tier=current_tier + 1)

if underlying_price <= lower_bound AND put_leg.state == LONG:
    # Execute T_lower_protocol  
    intent = Intent(ENTER_SHORT_ATM_CE, tier=current_tier + 1)
```

**Key Insight:** T2 doesn't have its own logic—it's a **hint generator** based on:
1. Underlying crossing bound
2. Opposite leg being LONG (active)

### 3.3 Interlock Rules (Cross-Leg Dependencies)

| Call State | Put State | Allowed Intents |
|------------|-----------|-----------------|
| SHORT | SHORT | None (initial entry only) |
| LONG | SHORT | Put can shift (T_upper/T_lower) |
| SHORT | LONG | Call can shift (T_upper/T_lower) |
| LONG | LONG | Both active, independent |
| SHIFTED | * | Opposite must be FLAT or LONG |

**Golden Rule:** Never have both legs in SHORT state after initial entry.

### 3.4 Action Zone Calculation

```python
# T1 Entry
premium = ce_price + pe_price
upper_bound = underlying + premium   # T2
lower_bound = underlying - premium   # T-2

# After T_upper_protocol (Put shifts)
new_premium = ce_price + new_pe_price
new_upper = underlying + new_premium  # T3
new_lower = underlying - new_premium  # T-3
```

## 4. Strategy Loop (Pure Function)

```python
def compute_intents(state: DeltaState, underlying_price: float) -> List[Intent]:
    """
    Pure function: Given state + underlying price, return intents.
    No broker calls. No quote fetching. No side effects.
    """
    intents = []
    
    # T1: Per-leg evaluation
    for leg in [state.call_leg, state.put_leg]:
        intent = evaluate_leg_state(leg, underlying_price, state.config)
        if intent != IntentType.NONE:
            intents.append(intent)
    
    # T2: Cross-leg triggers
    if underlying_price >= state.upper_bound and state.call_leg.state == LegState.LONG:
        intents.append(Intent(ENTER_SHORT_ATM_PE, "PE", "t2_trigger", state.tier + 1))
    
    elif underlying_price <= state.lower_bound and state.put_leg.state == LegState.LONG:
        intents.append(Intent(ENTER_SHORT_ATM_CE, "CE", "t2_trigger", state.tier + 1))
    
    # Apply interlock rules (filter conflicting intents)
    intents = apply_interlock_filter(intents, state)
    
    return intents
```

## 5. Order Manager Interface

```python
class OrderManager:
    def __init__(self, broker_api, symbol_helper, config: StrategyConfig):
        self.api = broker_api
        self.symbols = symbol_helper  # Can resolve ATM strikes
        self.config = config
        self.quote_cache = {}         # instrument_token → price
    
    def execute(self, intent: Intent, underlying_price: float) -> ExecutionResult:
        """
        Translates Intent into broker orders.
        Handles: instrument resolution, quote fetching, order placement.
        """
        match intent.intent_type:
            case IntentType.ENTER_SHORT_ATM_CE:
                strike = self.symbols.get_atm_strike(underlying_price, "CE")
                return self._enter_short(strike, "CE")
            
            case IntentType.ENTER_SHORT_ATM_PE:
                strike = self.symbols.get_atm_strike(underlying_price, "PE")
                return self._enter_short(strike, "PE")
            
            case IntentType.EXIT_POSITION:
                return self._exit(intent.option_type)
            
            case IntentType.SHIFT_STRIKE:
                return self._shift_strike(intent.option_type, underlying_price)
    
    def _enter_short(self, strike: int, option_type: str) -> ExecutionResult:
        # 1. Resolve instrument
        symbol = f"BTC{strike}{option_type}"
        token = self.symbols.get_token(symbol)
        
        # 2. Fetch quote (subscribe on-demand if needed)
        price = self._get_quote(token)
        
        # 3. Place orders
        short_id = self.api.order_place(
            symbol=symbol,
            side="SELL",
            order_type="MARKET",
            quantity=self.config.quantity
        )
        
        sl_id = self.api.order_place(
            symbol=symbol,
            side="BUY",
            order_type="SL",
            quantity=self.config.quantity * 2,
            trigger_price=price + self.config.stop_loss,
            price=price + self.config.stop_loss + self.config.slippage
        )
        
        return ExecutionResult(short_id, sl_id, price)
    
    def _get_quote(self, instrument_token: str, timeout_ms: int = 500) -> float:
        """
        Subscribe to quote on-demand and wait for tick.
        Caches result for subsequent calls.
        """
        if instrument_token not in self.quote_cache:
            self.ws.subscribe([instrument_token])
            # Wait for tick...
            self.quote_cache[instrument_token] = price
        
        return self.quote_cache[instrument_token]
```

## 6. State Machine Diagram

```
                    ┌──────────────────────────────────────────┐
                    │              INITIAL ENTRY               │
                    │  Intent: ENTER_SHORT_ATM_CE + PE         │
                    └─────────────────┬────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
            ┌───────────────┐                   ┌───────────────┐
            │  CE: SHORT    │                   │  PE: SHORT    │
            │  PE: SHORT    │                   │  CE: SHORT    │
            └───────┬───────┘                   └───────┬───────┘
                    │                                   │
        SL Hit ────┘                           SL Hit ──┘
                    │                                   │
                    ▼                                   ▼
            ┌───────────────┐                   ┌───────────────┐
            │  CE: LONG     │                   │  PE: LONG     │
            │  PE: SHORT    │  ← T1 active      │  CE: SHORT    │  ← T1 active
            │  (SAR)        │                   │  (SAR)        │
            └───────┬───────┘                   └───────┬───────┘
                    │                                   │
        ┌───────────┼───────────┐           ┌───────────┼───────────┐
        │           │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼           ▼
   SL Hit     Target      TTL+Profit  SL Hit     Target    TTL+Profit
        │           │           │           │           │           │
        ▼           ▼           ▼           │           │           │
   ┌────────┐  ┌────────┐  ┌────────┐       │           │           │
   │ SHORT  │  │SHIFTED │  │  FLAT  │       │           │           │
   │ (SAR)  │  │(ITM)   │  │        │       │           │           │
   └────────┘  └───┬────┘  └────────┘       │           │           │
                   │                        │           │           │
                   └────────────────────────┘           │           │
                            │                           │           │
                            ▼                           ▼           ▼
                    T2 Trigger: underlying crosses bound + opposite is LONG
                            │
                            ▼
                    ┌───────────────────┐
                    │  T_upper_protocol │  or  │  T_lower_protocol │
                    │  Shift Put UP     │      │  Shift Call DOWN  │
                    └───────────────────┘
```

## 7. Orchestrator Pattern (main.py)

```python
def main():
    # 1. Initialize components
    config = get_config()
    logging = set_logger(config.log)
    broker = get_broker(config, logging)
    symbols = Symbols(logging, **config.symbol_settings)
    
    # 2. Subscribe to underlying quote stream ONCE
    underlying_token = symbols.get_underlying_token()
    ws = WebSocketManager(broker, symbols, logging)
    ws.subscribe([underlying_token])
    
    # 3. Load or initialize state
    state = load_state() or initialize_state(config, symbols)
    
    # 4. Create order manager (has its own ws for on-demand subscriptions)
    order_manager = OrderManager(broker, symbols, ws, config, logging)
    
    # 5. Run delta strategy (internal while loop)
    delta = Delta(state, order_manager, config, logging)
    delta.run()
```

## 8. Delta.run() Internal Loop

```python
class Delta:
    def __init__(self, state, order_manager, config, logging):
        self.state = state
        self.order_manager = order_manager
        self.config = config
        self.logging = logging
    
    def run(self):
        while not is_time_past(self.config.program.stop):
            # 1. Get fresh underlying price (already subscribed)
            underlying_quote = self.order_manager.get_quote(
                self.state.underlying_token
            )
            underlying_price = underlying_quote.last_price
            
            # 2. Compute intents from state + underlying price
            intents = self.compute_intents(self.state, underlying_price)
            
            # 3. Execute each intent (order manager handles symbol subscription)
            for intent in intents:
                result = self.order_manager.execute(intent, underlying_price)
                
                # 4. Update state based on execution
                self.update_state(intent, result)
                
                # 5. Persist state to disk
                save_state(self.state)
            
            blink()  # Wait for next tick
        
        # Cleanup on exit
        self.cleanup()
    
    def compute_intents(self, state, underlying_price) -> List[Intent]:
        """Pure function: state + price → intents"""
        intents = []
        
        # T1: Per-leg evaluation
        for leg in [state.call_leg, state.put_leg]:
            intent = self._evaluate_leg(leg, state)
            if intent:
                intents.append(intent)
        
        # T2: Cross-leg triggers
        if underlying_price >= state.upper_bound and state.call_leg.state == LegState.LONG:
            intents.append(Intent(IntentType.ENTER_SHORT_ATM_PE, "PE", "t2_trigger"))
        
        elif underlying_price <= state.lower_bound and state.put_leg.state == LegState.LONG:
            intents.append(Intent(IntentType.ENTER_SHORT_ATM_CE, "CE", "t2_trigger"))
        
        return self._apply_interlock(intents, state)
```

## 9. Order Manager: On-Demand Subscription

```python
class OrderManager:
    def __init__(self, broker, symbols, ws, config, logging):
        self.api = broker
        self.symbols = symbols
        self.ws = ws  # Shared websocket
        self.config = config
        self.logging = logging
        self._quote_cache = {}
    
    def execute(self, intent: Intent, underlying_price: float) -> ExecutionResult:
        """Execute intent: resolve symbol → subscribe → get quote → place orders"""
        
        match intent.intent_type:
            case IntentType.ENTER_SHORT_ATM_CE | IntentType.ENTER_SHORT_ATM_PE:
                strike = self.symbols.get_atm_strike(underlying_price, intent.option_type)
                return self._enter_short(strike, intent.option_type)
            
            case IntentType.EXIT_POSITION:
                return self._exit(intent.option_type)
            
            case IntentType.SHIFT_STRIKE:
                return self._shift_strike(intent.option_type, underlying_price)
    
    def _enter_short(self, strike: int, option_type: str) -> ExecutionResult:
        # 1. Resolve symbol
        symbol = self.symbols.build_option_symbol(strike, option_type)
        token = self.symbols.get_token(symbol)
        
        # 2. Subscribe on-demand (websocket handles duplicates)
        self.ws.subscribe([token])
        
        # 3. Get quote (blocks until tick arrives)
        price = self._get_quote(token)
        
        # 4. Place short order
        short_id = self.api.order_place(
            symbol=symbol,
            side="SELL",
            order_type="MARKET",
            quantity=self.config.quantity
        )
        
        # 5. Place SL order (quantity * 2 for SAR)
        sl_id = self.api.order_place(
            symbol=symbol,
            side="BUY",
            order_type="SL",
            quantity=self.config.quantity * 2,
            trigger_price=price + self.config.stop_loss,
            price=price + self.config.stop_loss + self.config.slippage
        )
        
        return ExecutionResult(short_id, sl_id, price, strike)
    
    def _get_quote(self, token: str, timeout_ms: int = 500) -> float:
        """Wait for quote from websocket (already subscribed)"""
        # Poll websocket cache until price arrives or timeout
        start = time.time()
        while time.time() - start < timeout_ms / 1000:
            price = self.ws.get_ltp(token)
            if price:
                self._quote_cache[token] = price
                return price
            time.sleep(0.05)
        raise QuoteTimeoutError(f"No quote for {token}")
```

## 10. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              main.py                                     │
│  1. Subscribe to underlying quote stream (ONCE)                         │
│  2. delta.run()                                                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Delta.run() [while loop]                        │
│                                                                         │
│  while not is_time_past(stop):                                          │
│    1. underlying_price = ws.get_ltp(underlying_token)  ← Already sub'd │
│    2. intents = compute_intents(state, underlying_price)                │
│    3. for intent in intents:                                            │
│         → order_manager.execute(intent, underlying_price)               │
│    4. update_state(intent, result)                                      │
│    5. save_state(state)  ← YAML to disk                                 │
│    6. blink()  ← Wait for next tick                                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    OrderManager.execute()                               │
│                                                                         │
│  1. Resolve symbol from intent hint                                     │
│     "ENTER_SHORT_ATM_CE" → strike lookup → "BTC50000CE"                │
│                                                                         │
│  2. Subscribe to option quote (on-demand)                               │
│     ws.subscribe([option_token])                                        │
│                                                                         │
│  3. Get quote (blocks 500ms max)                                        │
│     price = _get_quote(option_token)                                    │
│                                                                         │
│  4. Place orders                                                        │
│     - short_id = order_place(SELL, MARKET)                              │
│     - sl_id = order_place(BUY, SL, qty*2)                               │
│                                                                         │
│  5. Return ExecutionResult                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## 11. Configuration Schema

```yaml
strategy:
  name: "delta"
  underlying: "BTCUSD"
  exchange: "delta_india"
  
  legs:
    - type: "CE"
    - type: "PE"
  
  risk:
    quantity: 1
    stop_loss: 500        # Points
    target: 1000          # Points
    slippage: 0.5         # %
    ttl_minutes: 30       # Time to live for T1 longs
  
  action_zones:
    initial_tier: 1
    expansion_factor: 1.0 # Premium multiplier for bounds
  
  program:
    start: "09:15"
    stop: "15:00"
    expiry_day: "last_thursday"
```

## 12. Implementation Checklist

- [ ] Create `LegState` enum and `Leg` dataclass
- [ ] Create `Intent` and `IntentType` for hints
- [ ] Implement `compute_intents()` as pure function (T1 + T2 rules)
- [ ] Implement `OrderManager` with on-demand quote subscription
- [ ] Implement interlock filter
- [ ] Create state persistence (YAML) - exclude order IDs
- [ ] Update `main.py` orchestrator pattern
- [ ] Refactor `Delta.run()` with internal while loop
- [ ] Write unit tests for each rule
- [ ] Add integration tests for full T1→T2 cycle

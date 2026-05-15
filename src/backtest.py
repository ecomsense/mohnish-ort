"""
Backtest Coinshort strategy using 1m historical candles from Delta Exchange.

Usage:
    uv run python -B src/backtest.py
"""

import json, os, sys, csv, types, math
from datetime import datetime
from traceback import print_exc
from unittest.mock import MagicMock

# ── Mock constants module (bypasses toolkit import issues) ────────────
bt_constants = types.ModuleType("constants")
bt_constants.get_logger = lambda name=None: __import__("logging").getLogger(name or "bt")
bt_constants.CNFG = {}
BT_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
bt_constants.S_DATA = BT_DATA + "/"
bt_constants.O_FUTL = MagicMock()
sys.modules["constants"] = bt_constants

sys.path.insert(0, os.path.dirname(__file__))

from sdk.models import Calls, Puts, LegState
from sdk.order_manager import OrderManager
from strategies.coinshort import Coinshort

# ── Config ────────────────────────────────────────────────────────────
SETTINGS = {
    "strategy": {"stop_loss": 150, "target": 150, "ttl": 15, "quantity": 1, "slippage": 0.5},
    "base_instrument": {"instrument_token": 1001, "tradingsymbol": "BTC-USD"},
}
UNDERLYING_TOKEN = 1001


class MockSymbols:
    def filter_by_moneyness(self, ltp: float, distance: int, option_type: str) -> list[dict]:
        diff = 100
        atm = round(ltp / diff) * diff
        strike = atm + distance * diff
        return [{
            "ws_token": str(strike + (100000 if option_type == "CE" else 200000)),
            "tradingsymbol": f"BTC-{strike}-{option_type}",
            "strike": strike,
        }]


class MockWsocket:
    def __init__(self):
        self.ltp: dict[str, float] = {}
    def subscribe(self, tokens: list[str]) -> None:
        for t in tokens:
            self.ltp.setdefault(t, 0.0)
    def connect(self, threaded: bool = True) -> None:
        pass


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class OptionPricer:
    """Black-Scholes pricer for April 24 monthly expiry at 70% IV."""

    EXPIRY_TS = 1777032000  # 2026-04-24 12:00 UTC
    IV = 0.70

    def __init__(self):
        self.entries: dict[str, dict] = {}

    def _dte(self, ts: int) -> float:
        return max(1, self.EXPIRY_TS - ts) / 365.25 / 86400

    def bs_price(self, strike: int, underlying: float, dte: float, opt_type: str) -> float:
        if dte <= 0:
            return max(0, underlying - strike) if opt_type == "CE" else max(0, strike - underlying)
        S, K, T = underlying, float(strike), dte
        if S <= 0 or K <= 0 or T <= 0:
            return 0.0
        v = self.IV
        d1 = (math.log(S / K) + 0.5 * v * v * T) / (v * math.sqrt(T))
        d2 = d1 - v * math.sqrt(T)
        if opt_type == "CE":
            return S * _norm_cdf(d1) - K * _norm_cdf(d2)
        else:
            return K * _norm_cdf(-d2) - S * _norm_cdf(-d1)

    def track(self, token: str, strike: int, underlying: float, premium: float, opt_type: str, ts: int) -> None:
        self.entries[str(token)] = dict(strike=strike, entry_ul=underlying, entry_prem=premium,
                                        opt_type=opt_type, entry_ts=ts)

    def estimate(self, token: str, underlying: float, ts: int) -> float:
        e = self.entries.get(str(token))
        if not e:
            atm_strike = round(underlying / 1000) * 1000
            dte = self._dte(ts)
            return self.bs_price(atm_strike, underlying, dte, "CE")
        dte = self._dte(ts)
        return self.bs_price(e["strike"], underlying, dte, e["opt_type"])

    def estimate_range(self, token: str, ul_low: float, ul_high: float, ts: int) -> tuple[float, float]:
        e = self.entries.get(str(token))
        if not e:
            return (0.0, 0.0)
        dte = self._dte(ts)
        lo = self.bs_price(e["strike"], ul_low, dte, e["opt_type"])
        hi = self.bs_price(e["strike"], ul_high, dte, e["opt_type"])
        return (min(lo, hi), max(lo, hi))


class BacktestBroker:
    def __init__(self, pricer: OptionPricer):
        self._orders: list[dict] = []
        self._fills: list[dict] = []
        self.pricer = pricer
        self._sym_to_token: dict[str, str] = {}
        self.current_underlying: float = 0.0
        self.current_ts: int = 0

    def authenticate(self) -> bool:
        return True

    @property
    def orders(self) -> list[dict]:
        return self._orders

    @property
    def trades(self) -> list[dict]:
        return [f for f in self._fills]

    def order_place(self, **kwargs) -> str | None:
        oid = f"o{len(self._orders)}_{kwargs.get('tag','')}"
        symbol = kwargs.get("symbol", "")
        side = kwargs.get("side", "BUY")
        otype = kwargs.get("order_type", "MARKET")
        qty = int(kwargs.get("quantity", 1))
        last_px = float(kwargs.get("last_price", 0))
        trig = float(kwargs.get("trigger_price", 0))

        is_market = otype[0].upper() == "M"
        fill = last_px if is_market else trig
        status = "COMPLETE" if is_market else "TRIGGER PENDING"

        order = dict(order_id=oid, symbol=symbol, side=side, quantity=qty,
                     order_type=otype, status=status, trigger_price=trig,
                     last_price=last_px, average_price=fill, tag=kwargs.get("tag", ""))
        self._orders.append(order)
        if is_market:
            self._fills.append(dict(ts=self.current_ts, order_id=oid, symbol=symbol, side=side,
                                    quantity=qty, average_price=fill, tag=kwargs.get("tag", "")))
        return oid

    def order_modify(self, **kwargs) -> dict | None:
        oid = kwargs.get("order_id")
        for o in self._orders:
            if o["order_id"] == oid:
                if kwargs.get("order_type") and kwargs["order_type"][0].upper() == "M":
                    o["order_type"] = "MARKET"
                    o["status"] = "COMPLETE"
                    o["average_price"] = o.get("last_price", o.get("trigger_price", 0))
                    self._fills.append(dict(ts=self.current_ts, order_id=oid, symbol=o["symbol"],
                                            side=o["side"], quantity=o["quantity"], average_price=o["average_price"], tag="modify"))
                return o
        return None

    def order_cancel(self, order_id: str) -> dict | None:
        for o in self._orders:
            if o["order_id"] == order_id:
                o["status"] = "CANCELLED"
                return o
        return None

    def set_sym_token(self, symbol: str, token: str) -> None:
        self._sym_to_token[symbol] = token

    def _token_for_symbol(self, symbol: str) -> str | None:
        return self._sym_to_token.get(symbol)

    def simulate_sl(self, low_ul: float, high_ul: float, ts: int = 0) -> None:
        pending = [o for o in self._orders if o["status"] == "TRIGGER PENDING" and o.get("trigger_price", 0) > 0]
        for o in pending:
            token = self._token_for_symbol(o["symbol"])
            if not token:
                continue
            opt_low, opt_high = self.pricer.estimate_range(token, low_ul, high_ul, ts or self.current_ts)
            trig = o["trigger_price"]
            if opt_low <= trig <= opt_high:
                o["status"] = "COMPLETE"
                o["average_price"] = trig
                self._fills.append(dict(ts=self.current_ts, order_id=o["order_id"], symbol=o["symbol"],
                                        side=o["side"], quantity=o["quantity"],
                                        average_price=trig, tag="sl_hit"))

    def find_fill_price(self, order_id: str) -> float:
        for f in self._fills:
            if f.get("order_id") == order_id:
                return float(f.get("average_price", 0))
        for o in self._orders:
            if o.get("order_id") == order_id and o["status"] in ("COMPLETE", "FILLED"):
                return float(o.get("average_price", 0))
        return 0.0


class BacktestRestapi:
    api_object: BacktestBroker | None = None

    @classmethod
    def api(cls) -> BacktestBroker:
        return cls.api_object

    def __init__(self, broker: BacktestBroker, quantity: int = 1):
        BacktestRestapi.api_object = broker
        from sdk.models import Order
        Order.set_quantity(quantity)

    def enter(self, kwargs: dict) -> str | None:
        return self.api().order_place(**kwargs)

    def find_fillprice_from_order_id(self, order_id: str) -> float:
        return self.api().find_fill_price(order_id)


class BacktestLogger:
    def __init__(self):
        self.ticks: list[dict] = []
        self.trades: list[dict] = []

    def tick(self, ts: int, underlying: float, cs: Coinshort) -> None:
        self.ticks.append(dict(time=ts, underlying=underlying, tier=cs.tier,
                               bounds=str(cs.bounds[-1] if cs.bounds else []),
                               ce_status=cs.ce.status.name if cs.ce.status else "FLAT",
                               pe_status=cs.pe.status.name if cs.pe.status else "FLAT",
                               current_premium=cs.current_premium, satellites=len(cs._satellites)))

    def trade(self, action: str, symbol: str, side: str, qty: int, price: float, reason: str, ts: int) -> None:
        self.trades.append(dict(time=ts, action=action, symbol=symbol,
                                side=side, qty=qty, price=price, reason=reason))

    def _write_csv(self, path: str, rows: list[dict]) -> None:
        if not rows:
            return
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    def save(self) -> None:
        bt_constants.S_DATA = bt_constants.S_DATA
        os.makedirs(bt_constants.S_DATA, exist_ok=True)
        self._write_csv(os.path.join(bt_constants.S_DATA, "backtest_log.csv"), self.ticks)
        self._write_csv(os.path.join(bt_constants.S_DATA, "backtest_trades.csv"), self.trades)


def run() -> None:
    print("Loading 1m candles...")
    path = os.path.join(bt_constants.S_DATA, "btc_1m_april2026.json")
    with open(path) as f:
        candles = json.load(f)
    print(f"Loaded {len(candles)} candles")

    pricer = OptionPricer()
    broker = BacktestBroker(pricer)
    ws = MockWsocket()
    logger = BacktestLogger()
    symbols = MockSymbols()
    api = BacktestRestapi(broker)
    config = SETTINGS["strategy"]

    om = OrderManager(ws=ws, symbols=symbols, api=api, config=config)

    # Patch: default option price for new tokens
    _orig_get_price = om._get_price

    def _bt_get_price(token: str) -> float:
        px = ws.ltp.get(token, 0.0)
        if px == 0.0 and broker.current_underlying:
            px = pricer.estimate(token, broker.current_underlying, broker.current_ts)
            ws.ltp[token] = px
        return px
    om._get_price = _bt_get_price

    # Patch: track options and symbol→token mapping
    _orig_enter = om.enter_short

    def _tracked_enter(underlying_price: float, option_type: str) -> dict:
        result = _orig_enter(underlying_price, option_type)
        if "error" not in result:
            token = result["token"]
            broker.set_sym_token(result["symbol"], token)
            pricer.track(token, result["strike"], underlying_price, result["price"], option_type, broker.current_ts)
            logger.trade("ENTER_SHORT", result["symbol"], "SELL",
                         config["quantity"], result["price"],
                         f"{option_type}_entry", broker.current_ts)
        return result
    om.enter_short = _tracked_enter

    strategy = Coinshort(
        config=config, symbols=symbols, api=api, om=om,
        underlying_token=UNDERLYING_TOKEN,
        underlying_symbol=SETTINGS["base_instrument"]["tradingsymbol"],
    )
    # Reset any loaded JSON state
    strategy.bounds = []
    strategy._entry_ce_id = None
    strategy._entry_pe_id = None
    strategy.ce = Calls()
    strategy.pe = Puts()
    strategy._satellites = []
    strategy.tier = 1
    strategy.current_premium = 0

    ws.subscribe([str(UNDERLYING_TOKEN)])

    print("Running backtest...")
    for idx, candle in enumerate(candles):
        ts = candle["time"]
        high, low, close = candle["high"], candle["low"], candle["close"]
        ws.ltp[str(UNDERLYING_TOKEN)] = close
        broker.current_underlying = close
        broker.current_ts = ts

        for tok in list(ws.ltp.keys()):
            if tok != str(UNDERLYING_TOKEN):
                ws.ltp[tok] = pricer.estimate(tok, close, ts)

        broker.simulate_sl(low, high, ts)

        try:
            strategy.tick(close)
        except Exception as e:
            print(f"  Error candle {idx}: {e}")
            print_exc()
            break

        if idx % 1440 == 0 or idx == len(candles) - 1:
            dt = datetime.fromtimestamp(ts)
            print(f"  [{dt:%m-%d %H:%M}] T{strategy.tier} "
                  f"CE={strategy.ce.status.name if strategy.ce.status else 'FLAT':>7} "
                  f"PE={strategy.pe.status.name if strategy.pe.status else 'FLAT':>7} "
                  f"@{close:.0f} bnd={strategy.bounds[-1] if strategy.bounds else '[]'} "
                  f"prem={strategy.current_premium:.0f} sats={len(strategy._satellites)}")

        logger.tick(ts, close, strategy)

    logger.save()

    net = 0
    for f in broker._fills:
        q, p = int(f.get("quantity", 1)), float(f.get("average_price", 0))
        net += p * q if f.get("side") == "SELL" else -p * q

    # MTM of open positions (unrealized P&L from theta decay)
    last_ts = candles[-1]["time"]
    last_close = candles[-1]["close"]
    mtm = 0.0
    def mtm_position(token, status, label):
        if status not in (LegState.SHORT, LegState.LONG, LegState.SHIFTED):
            return 0.0
        e = pricer.entries.get(str(token))
        if not e:
            return 0.0
        current = pricer.bs_price(e["strike"], last_close, pricer._dte(last_ts), e["opt_type"])
        if status in (LegState.SHORT, LegState.SHIFTED):
            pnl = e["entry_prem"] - current
        else:
            pnl = current - e["entry_prem"]
        print(f"  MTM {label}: entry={e['entry_prem']:.0f} current={current:.0f} pnl={pnl:+.0f}")
        return pnl

    print(f"\n  --- Open positions MTM ---")
    mtm += mtm_position(strategy.ce.instrument_token, strategy.ce.status, "CE")
    mtm += mtm_position(strategy.pe.instrument_token, strategy.pe.status, "PE")
    for sat in strategy._satellites:
        if sat["status"] in (LegState.SHORT, LegState.SHIFTED):
            tok = str(sat.get("instrument_token", 0))
            mtm += mtm_position(tok, sat["status"], f"SAT T{sat.get('tier','?')} {sat.get('option_type','?')}")

    total_pnl = net + mtm

    print(f"\n{'='*60}")
    print(f"BACKTEST SUMMARY")
    print(f"{'='*60}")
    print(f"  Candles:     {len(candles)}")
    print(f"  Final tier:  T{strategy.tier}")
    print(f"  CE:          {strategy.ce.status.name if strategy.ce.status else 'FLAT'}")
    print(f"  PE:          {strategy.pe.status.name if strategy.pe.status else 'FLAT'}")
    print(f"  Bounds:      {strategy.bounds[-1] if strategy.bounds else 'N/A'}")
    print(f"  Premium:     {strategy.current_premium:.0f}")
    print(f"  Satellites:  {len(strategy._satellites)}")
    print(f"  Net P&L:     {net:.0f}")
    print(f"  Fills:       {len(broker._fills)}")
    print(f"  Realized P&L: {net:.0f}")
    print(f"  MTM P&L:      {mtm:+.0f}")
    print(f"  Total P&L:    {total_pnl:.0f}")

    # Write fills CSV for daily P&L analysis
    fills_path = os.path.join(bt_constants.S_DATA, "backtest_fills.csv")
    with open(fills_path, "w", newline="") as f:
        if broker._fills:
            w = csv.DictWriter(f, fieldnames=list(broker._fills[0].keys()))
            w.writeheader()
            w.writerows(broker._fills)

    with open(os.path.join(bt_constants.S_DATA, "backtest_outcome.txt"), "w") as f:
        f.write(f"Candles: {len(candles)}\nFinal tier: T{strategy.tier}\n")
        f.write(f"CE: {strategy.ce.status}\nPE: {strategy.pe.status}\n")
        f.write(f"Bounds: {strategy.bounds}\nPremium: {strategy.current_premium:.0f}\n")
        f.write(f"Satellites: {len(strategy._satellites)}\nNet P&L: {net:.0f}\nMTM P&L: {mtm:+.0f}\nTotal P&L: {total_pnl:.0f}\nFills: {len(broker._fills)}\n")
        f.write("\n=== FILL LOG ===\n")
        for fill in broker._fills:
            f.write(f"  {fill.get('order_id',''):>14} {fill.get('side',''):>5} {fill.get('symbol',''):>22} "
                    f"q={fill.get('quantity','')} px={float(fill.get('average_price',0)):>8.0f} {fill.get('tag','')}\n")

    print(f"\nLogs saved to {bt_constants.S_DATA}")


if __name__ == "__main__":
    run()

"""
Live-price backtest using real May 29 option candles.

Fetch real 1h option candles for all ATM-range strikes, then run the
strategy using actual market prices (not modelled).
"""

import json
import os
import sys
import csv
import types
import bisect
import requests
import pendulum
from collections import defaultdict
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

btc = types.ModuleType("constants")
btc.get_logger = lambda n=None: __import__("logging").getLogger(n or "bt")
btc.CNFG = {}
btc.S_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data") + "/"
btc.O_FUTL = MagicMock()
sys.modules["constants"] = btc

from sdk.models import Calls, Puts, LegState
from sdk.order_manager import OrderManager
from strategies.coinshort import Coinshort

API = "https://api.india.delta.exchange"


def fetch_option_candles(symbol, resolution, start_ts, end_ts):
    """Fetch option candles from Delta API."""
    all_c = []
    cursor = start_ts
    while cursor < end_ts:
        chunk_end = min(cursor + 2000 * {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}[resolution], end_ts)
        r = requests.get(f"{API}/v2/history/candles", params={
            "symbol": symbol, "resolution": resolution,
            "start": cursor, "end": chunk_end
        }, timeout=15)
        data = r.json()
        candles = data.get("result", [])
        if not candles:
            break
        all_c.extend(candles)
        cursor = chunk_end
    return all_c


def fetch_btc_candles(resolution, start_ts, end_ts):
    return fetch_option_candles("BTCUSD", resolution, start_ts, end_ts)


def fetch_option_chain():
    """Get all May 29 BTC option symbols and their strikes."""
    r = requests.get(f"{API}/v2/products", params={
        "contract_types": "call_options,put_options",
        "expiry": "2026-05-29"
    }, timeout=15)
    opts = [p for p in r.json().get("result", [])
            if p.get("underlying_asset", {}).get("symbol") == "BTC"]
    symbols = {}
    for p in opts:
        sym = p["symbol"]
        strike = int(p.get("strike_price", 0))
        otype = "CE" if sym.startswith("C-") else "PE"
        symbols[sym] = {"strike": strike, "type": otype}
    return symbols


class RealPricer:
    def __init__(self, price_db, token_to_symbol=None):
        self.price_db = price_db
        self.token_to_symbol = token_to_symbol or {}
        self.entries = {}

    def price_at(self, symbol, ts):
        prices = self.price_db.get(symbol, {})
        if not prices:
            return 0.0
        timestamps = sorted(prices.keys())
        idx = bisect.bisect_right(timestamps, ts) - 1
        if idx < 0:
            idx = 0
        return prices[timestamps[idx]]

    def estimate(self, token, underlying, ts):
        sym = self.token_to_symbol.get(str(token), str(token))
        return self.price_at(sym, ts)

    def track(self, token, strike, underlying, premium, opt_type, ts):
        self.entries[str(token)] = dict(strike=strike, entry_ul=underlying,
                                        entry_prem=premium, opt_type=opt_type, entry_ts=ts)

    def estimate_range(self, token, lo, hi, ts):
        p = self.estimate(token, ts)
        return (p * 0.95, p * 1.05)


class MockSymbols:
    def filter_by_moneyness(self, ltp, dist, opt_type):
        diff = 1000  # May 29 strikes are every 1000
        atm = round(ltp / diff) * diff
        strike = atm + dist * diff
        token = strike * 10 + (1 if opt_type == "CE" else 2)
        return [{
            "ws_token": str(token),
            "tradingsymbol": f"BTC-{strike}-{opt_type}",
            "strike": strike,
        }]


class MockWsocket:
    def __init__(self):
        self.ltp = {}
    def subscribe(self, ts):
        for t in ts:
            self.ltp.setdefault(t, 0.0)
    def connect(self, t=True):
        pass


class Broker:
    def __init__(self, pricer):
        self._o = []; self._f = []; self.p = pricer
        self._s2t = {}; self.cul = 0.0; self.current_ts = 0
    def authenticate(self): return True
    @property
    def orders(self): return self._o
    def order_place(self, **kw):
        oid = f"o{len(self._o)}_{kw.get('tag','')}"
        sym = kw["symbol"]; sd = kw["side"]; ot = kw["order_type"]
        q = int(kw.get("quantity", 1)); lp = float(kw.get("last_price", 0))
        tr = float(kw.get("trigger_price", 0))
        ism = ot[0].upper() == "M"
        fl = lp if ism else tr; st = "COMPLETE" if ism else "TRIGGER PENDING"
        self._o.append(dict(order_id=oid, symbol=sym, side=sd, quantity=q,
                            order_type=ot, status=st, trigger_price=tr,
                            last_price=lp, average_price=fl, tag=kw.get("tag","")))
        if ism:
            self._f.append(dict(ts=self.current_ts, ul=self.cul, order_id=oid, symbol=sym,
                                side=sd, quantity=q, average_price=fl, tag=kw.get("tag","")))
        return oid
    def order_modify(self, **kw):
        oid = kw["order_id"]
        for o in self._o:
            if o["order_id"] != oid: continue
            if kw.get("order_type") and kw["order_type"][0].upper() == "M":
                o["order_type"] = "MARKET"; o["status"] = "COMPLETE"
                o["average_price"] = o.get("last_price", o.get("trigger_price", 0))
                self._f.append(dict(ts=self.current_ts, ul=self.cul, order_id=oid, symbol=o["symbol"],
                                    side=o["side"], quantity=o["quantity"],
                                    average_price=o["average_price"], tag="modify"))
            return o
        return None
    def order_cancel(self, oid):
        for o in self._o:
            if o["order_id"] == oid: o["status"] = "CANCELLED"; return o
        return None
    def set_sym_tok(self, s, t): self._s2t[s] = t
    def sim_sl(self, lo, hi, ts):
        for o in self._o:
            if o["status"] != "TRIGGER PENDING" or not o.get("trigger_price"): continue
            tok = self._s2t.get(o["symbol"]); tr = o["trigger_price"]
            if not tok: continue
            cp = self.p.estimate(tok, self.cul, ts)
            if cp >= tr:
                o["status"] = "COMPLETE"; o["average_price"] = tr
                qty = o["quantity"]
                tag = o.get("tag", "")
                if qty >= 2 and tag == "stoploss":
                    self._f.append(dict(ts=ts, ul=self.cul, order_id=o["order_id"]+"_sl", symbol=o["symbol"],
                                        side=o["side"], quantity=1,
                                        average_price=tr, tag="sl_hit"))
                    self._f.append(dict(ts=ts, ul=self.cul, order_id=o["order_id"]+"_el", symbol=o["symbol"],
                                        side=o["side"], quantity=1,
                                        average_price=tr, tag="enter_long"))
                else:
                    self._f.append(dict(ts=ts, ul=self.cul, order_id=o["order_id"], symbol=o["symbol"],
                                        side=o["side"], quantity=qty,
                                        average_price=tr, tag="sl_hit"))
    def find_fill(self, oid):
        for f in self._f:
            if f["order_id"] == oid: return float(f["average_price"])
        for o in self._o:
            if o["order_id"] == oid and o["status"] in ("COMPLETE","FILLED"):
                return float(o["average_price"])
        return 0.0


class Restapi:
    api_object = None
    @classmethod
    def api(cls): return cls.api_object
    def __init__(self, broker, q=1):
        Restapi.api_object = broker
        from sdk.models import Order; Order.set_quantity(q)
    def enter(self, kw): return self.api().order_place(**kw)
    def find_fillprice_from_order_id(self, oid): return self.api().find_fill(oid)


def run():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    resolution = "1h"  # 1h candles

    # Date range: Apr 25 (day after Apr 24 monthly expiry) to May 16 (today)
    start_dt = pendulum.datetime(2026, 4, 25, 0, 0, tz='UTC')
    end_dt = pendulum.datetime(2026, 5, 16, 0, 0, tz='UTC')
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    print("Fetching BTC 1h candles...")
    btc_candles = fetch_btc_candles(resolution, start_ts, end_ts)
    btc_candles.sort(key=lambda c: c["time"])  # ascending order
    print(f"  {len(btc_candles)} BTC candles from {pendulum.from_timestamp(btc_candles[0]['time']).format('YYYY-MM-DD')} to {pendulum.from_timestamp(btc_candles[-1]['time']).format('YYYY-MM-DD')}")

    print("Fetching May 29 option chain...")
    chain = fetch_option_chain()
    print(f"  {len(chain)} option symbols")

    # Determine ATM strike range: BTC ranged ~68000-79000
    # Need strikes from ~65000 to ~82000
    needed_strikes = range(65000, 83000, 1000)
    needed_syms = [s for s, info in chain.items()
                   if info["strike"] in needed_strikes]
    print(f"  Fetching 1h candles for {len(needed_syms)} ATM-range symbols...")

    price_db = defaultdict(dict)  # {symbol: {ts: close_price}}
    for i, sym in enumerate(needed_syms):
        candles = fetch_option_candles(sym, resolution, start_ts, end_ts)
        for c in candles:
            price_db[sym][c["time"]] = c["close"]
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(needed_syms)} done")
    print(f"  Done. {sum(len(v) for v in price_db.values())} total price points")

    # Save price DB
    price_db_serializable = {k: dict(v) for k, v in price_db.items()}
    with open(os.path.join(data_dir, "option_prices_may.json"), "w") as f:
        json.dump(price_db_serializable, f)
    print("  Saved to option_prices_may.json")

    # Build mock token→symbol mapping (numeric tokens)
    token_to_symbol = {}
    for sym in needed_syms:
        strike = chain[sym]["strike"]
        otype = chain[sym]["type"]
        token = str(strike * 10 + (1 if otype == "CE" else 2))
        token_to_symbol[token] = sym

    # --- BACKTEST ---
    pricer = RealPricer(price_db, token_to_symbol)
    broker = Broker(pricer)
    ws = MockWsocket()
    sm = MockSymbols()
    api = Restapi(broker)
    config = {"stop_loss": 150, "target": 150, "ttl": 15, "quantity": 1, "slippage": 0.5}
    om = OrderManager(ws=ws, symbols=sm, api=api, config=config)

    # Patch get_price to use real option data
    def _bt_gp(token):
        px = ws.ltp.get(token, 0.0)
        if px == 0.0 and broker.current_ts:
            sym = token_to_symbol.get(token)
            if sym:
                px = pricer.price_at(sym, broker.current_ts)
                ws.ltp[token] = px
        return px
    om._get_price = _bt_gp

    _oe = om.enter_short
    def _te(ul, ot):
        r = _oe(ul, ot)
        if "error" not in r:
            broker.set_sym_tok(r["symbol"], r["token"])
            pricer.track(r["token"], r["strike"], ul, r["price"], ot, broker.current_ts)
        return r
    om.enter_short = _te

    strategy = Coinshort(config=config, symbols=sm, api=api, om=om,
                         underlying_token=1001, underlying_symbol="BTC-USD")
    strategy.bounds = []; strategy._entry_ce_id = None; strategy._entry_pe_id = None
    strategy.ce = Calls(); strategy.pe = Puts(); strategy._satellites = []
    strategy.tier = 1; strategy.current_premium = 0
    ws.subscribe(["1001"])

    print("\nRunning backtest with REAL option prices...")
    for idx, candle in enumerate(btc_candles):
        ts = candle["time"]
        close = candle["close"]
        ws.ltp["1001"] = close
        broker.cul = close
        broker.current_ts = ts

        # Update option LTPs from real data
        for tok in list(ws.ltp.keys()):
            if tok != "1001":
                sym = token_to_symbol.get(tok)
                if sym:
                    ws.ltp[tok] = pricer.price_at(sym, ts)

        broker.sim_sl(candle.get("low", close), candle.get("high", close), ts)

        try:
            strategy.tick(close)
        except Exception as e:
            print(f"  Error at candle {idx}: {e}")
            import traceback; traceback.print_exc()
            break

        if idx % 168 == 0 or idx == len(btc_candles) - 1:
            dt = pendulum.from_timestamp(ts)
            print(f"  [{dt.format('MM-DD HH:mm')}] T{strategy.tier} "
                  f"CE={strategy.ce.status.name if strategy.ce.status else 'FLAT':>7} "
                  f"PE={strategy.pe.status.name if strategy.pe.status else 'FLAT':>7} "
                  f"@{close:.0f} bnd={strategy.bounds[-1] if strategy.bounds else '[]'} "
                  f"prem={strategy.current_premium:.0f} sats={len(strategy._satellites)}")

    # P&L
    net = 0

    # Save tradebook CSV
    tradebook_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tradebook_may.csv")
    with open(tradebook_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "datetime", "underlying", "side", "symbol", "qty", "opt_price", "reason", "type"])
        for fill in broker._f:
            ts = fill.get("ts", 0)
            dt = pendulum.from_timestamp(ts).format("MM-DD HH:mm") if ts else ""
            ul = fill.get("ul", "")
            side = fill.get("side", "")
            sym = fill.get("symbol", "")
            qty = fill.get("quantity", 1)
            px = fill.get("average_price", 0)
            tag = fill.get("tag", "")
            # Determine type from tag and side
            ftype = tag if tag else "enter_short"
            w.writerow([ts, dt, ul, side, sym, qty, px, tag, ftype])
    for f in broker._f:
        q, p = int(f.get("quantity", 1)), float(f.get("average_price", 0))
        net += p * q if f.get("side") == "SELL" else -p * q

    print(f"\n{'='*50}")
    print("REAL BACKTEST RESULTS (May 29 options, 1h candles)")
    print(f"{'='*50}")
    print(f"  Period:     {start_dt.format('YYYY-MM-DD')} to {end_dt.format('YYYY-MM-DD')}")
    print(f"  Final tier: T{strategy.tier}")
    print(f"  CE:         {strategy.ce.status.name if strategy.ce.status else 'FLAT'}")
    print(f"  PE:         {strategy.pe.status.name if strategy.pe.status else 'FLAT'}")
    print(f"  Bounds:     {strategy.bounds[-1] if strategy.bounds else 'N/A'}")
    print(f"  Premium:    {strategy.current_premium:.0f}")
    print(f"  Fills:      {len(broker._f)}")
    print(f"  Realized P&L: {net:.0f}")

    # MTM on open positions
    last_ts = btc_candles[-1]["time"]
    last_close = btc_candles[-1]["close"]
    mtm = 0.0
    print("\n  --- Open positions MTM ---")
    for label, token, status in [
        ("CE", strategy.ce.instrument_token, strategy.ce.status),
        ("PE", strategy.pe.instrument_token, strategy.pe.status),
    ] + [("SAT T{s[o.get('tier','?')]} {s[o.get('option_type','?')]}".format(s=s), s.get("instrument_token", 0), s["status"])
         for s in strategy._satellites if s["status"] in (LegState.SHORT, LegState.SHIFTED)]:
        if status not in (LegState.SHORT, LegState.LONG, LegState.SHIFTED):
            continue
        e = pricer.entries.get(str(token))
        if not e:
            continue
        sym = token_to_symbol.get(str(token))
        curr = pricer.price_at(sym, last_ts) if sym else 0.0
        if status in (LegState.SHORT, LegState.SHIFTED):
            pnl = e["entry_prem"] - curr
        else:
            pnl = curr - e["entry_prem"]
        mtm += pnl
        print(f"    {label}: entry={e['entry_prem']:.0f} current={curr:.0f} mtm={pnl:+.0f}")
    print(f"    Total MTM: {mtm:+.0f}")
    print(f"  Total P&L:    {net + mtm:.0f}")

    # Daily P&L
    daily = defaultdict(float)
    for f in broker._f:
        ts = f.get("ts", 0)
        if not ts: continue
        day = pendulum.from_timestamp(ts).format("MM-DD ddd")
        q, p = int(f.get("quantity", 1)), float(f.get("average_price", 0))
        daily[day] += p * q if f.get("side") == "SELL" else -p * q

    print("\n  --- Daily P&L ---")
    cum = 0
    for day in sorted(daily):
        cum += daily[day]
        print(f"    {day}: {daily[day]:>+8.0f} (cumul: {cum:>+8.0f})")


if __name__ == "__main__":
    run()

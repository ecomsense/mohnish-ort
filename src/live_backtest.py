"""
Generic live backtester for Coinshort strategy.

Usage:
    uv run python src/live_backtest.py

Downloads 1m candle data and runs backtest against the current monthly expiry.
Output: data/tradebook_live.csv
"""

import json, os, sys, csv, types, bisect, requests, pendulum, re, time
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
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def detect_monthly_expiry():
    """Auto-detect the next monthly option expiry that is live."""
    r = requests.get(f"{API}/v2/products", params={
        "contract_types": "call_options,put_options",
        "states": "live"
    }, timeout=15)
    opts = r.json().get("result", [])
    expiries = set()
    for p in opts:
        st = (p.get("settlement_time") or "")[:10]
        if st:
            expiries.add(st)
    if not expiries:
        raise RuntimeError("No live option expiries found")
    # Pick the nearest monthly (last trading day of a month)
    today = pendulum.today("UTC")
    monthly = None
    for e in sorted(expiries):
        dt = pendulum.from_format(e, "YYYY-MM-DD")
        if dt >= today and (dt.day >= 24 or dt == dt.end_of("month")):
            monthly = e
            break
    if not monthly:
        monthly = sorted(expiries)[0]
    return monthly


def fetch_candles(symbol, resolution, start, end, delay=0.05):
    """Fetch candle data with pagination."""
    all_c = []
    cursor = start
    while cursor < end:
        chunk = min(cursor + 86400, end)
        try:
            r = requests.get(f"{API}/v2/history/candles", params={
                "symbol": symbol, "resolution": resolution,
                "start": cursor, "end": chunk
            }, timeout=15)
            candles = r.json().get("result", [])
            all_c.extend(candles)
        except Exception as e:
            print(f"    WARN: {e}")
        cursor = chunk
        time.sleep(delay)
    all_c.sort(key=lambda c: c["time"])
    return all_c


def download_data(expiry_str, start_dt=None):
    """Download 1m BTC and option candles."""
    expiry_dt = pendulum.from_format(expiry_str, "YYYY-MM-DD")
    end_dt = pendulum.today("UTC")
    if start_dt is None:
        start_dt = expiry_dt.subtract(days=35)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    print(f"\nDownloading 1m BTC candles: {start_dt.format('MM-DD')} → {end_dt.format('MM-DD')}")
    btc_candles = fetch_candles("BTCUSD", "1m", start_ts, end_ts)
    print(f"  {len(btc_candles)} candles")

    # Get option chain for this expiry
    print(f"\nFetching option chain for {expiry_str}...")
    r = requests.get(f"{API}/v2/products", params={
        "contract_types": "call_options,put_options", "expiry": expiry_str
    }, timeout=15)
    opts = [p for p in r.json().get("result", [])
            if p.get("underlying_asset", {}).get("symbol") == "BTC"]
    chain = {}
    for p in opts:
        s = p["symbol"]
        strike = int(p.get("strike_price", 0))
        opt_type = "CE" if s.startswith("C-") else "PE"
        chain[s] = {"strike": strike, "type": opt_type}
    print(f"  {len(chain)} symbols")

    # Download 1m candles for ATM-range strikes
    strikes_range = range(50000, 120000, 1000)
    needed = [s for s, info in chain.items() if info["strike"] in strikes_range]
    print(f"  Downloading {len(needed)} ATM-range symbols (1m)...")

    price_db = {}
    for i, sym in enumerate(needed):
        candles = fetch_candles(sym, "1m", start_ts, end_ts, delay=0.05)
        price_db[sym] = {c["time"]: c["close"] for c in candles}
        if (i + 1) % 10 == 0:
            total_pts = sum(len(v) for v in price_db.values())
            print(f"    {i+1}/{len(needed)} — {total_pts} price points")

    total = sum(len(v) for v in price_db.values())
    print(f"\n  Total: {len(price_db)} symbols, {total} price points")

    # Save
    out = {"expiry": expiry_str, "start_ts": start_ts, "end_ts": end_ts,
           "btc_candles": btc_candles, "option_prices": price_db}
    path = os.path.join(DATA_DIR, "live_backtest_data.json")
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"  Saved to live_backtest_data.json")
    return out


# ── Backtest classes ─────────────────────────────────────────────────────

class MockSymbols:
    def filter_by_moneyness(self, ltp, dist, opt_type):
        diff = 1000
        atm = round(ltp / diff) * diff
        strike = atm + dist * diff
        token = strike * 10 + (1 if opt_type == "CE" else 2)
        return [{"ws_token": str(token), "tradingsymbol": f"BTC-{strike}-{opt_type}", "strike": strike}]


class MockWsocket:
    def __init__(self):
        self.ltp = {}
    def subscribe(self, ts):
        for t in ts:
            self.ltp.setdefault(t, 0.0)
    def connect(self, t=True):
        pass


class Pricer:
    def __init__(self, price_db, token_to_symbol):
        self.price_db = price_db
        self.token_to_symbol = token_to_symbol
        self.entries = {}
    def price_at(self, symbol, ts):
        prices = self.price_db.get(symbol, {})
        if not prices:
            return 0.0
        tss = sorted(int(k) for k in prices.keys())
        idx = bisect.bisect_right(tss, ts) - 1
        if idx < 0:
            return float(prices[str(tss[0])])
        return float(prices[str(tss[idx])])
    def estimate(self, token, underlying, ts):
        sym = self.token_to_symbol.get(str(token), str(token))
        return self.price_at(sym, ts)
    def track(self, token, strike, underlying, premium, opt_type, ts):
        self.entries[str(token)] = dict(strike=strike, entry_ul=underlying,
                                        entry_prem=premium, opt_type=opt_type, entry_ts=ts)


class Broker:
    def __init__(self, pricer):
        self._o = []; self._f = []; self.p = pricer
        self._s2t = {}; self.cul = 0.0; self.current_ts = 0
    def authenticate(self):
        return True
    @property
    def orders(self):
        return self._o
    def order_place(self, **kw):
        oid = f"o{len(self._o)}_{kw.get('tag','')}"
        sym, sd, ot = kw["symbol"], kw["side"], kw["order_type"]
        q = int(kw.get("quantity", 1))
        lp, tr = float(kw.get("last_price", 0)), float(kw.get("trigger_price", 0))
        ism = ot[0].upper() == "M"
        fl, st = (lp if ism else tr), ("COMPLETE" if ism else "TRIGGER PENDING")
        self._o.append(dict(order_id=oid, symbol=sym, side=sd, quantity=q,
                            order_type=ot, status=st, trigger_price=tr,
                            last_price=lp, average_price=fl, tag=kw.get("tag","")))
        if ism:
            self._f.append(dict(ts=self.current_ts, ul=self.cul, order_id=oid,
                                symbol=sym, side=sd, quantity=q,
                                average_price=fl, tag=kw.get("tag","")))
        return oid
    def order_modify(self, **kw):
        oid = kw["order_id"]
        for o in self._o:
            if o["order_id"] != oid:
                continue
            if kw.get("order_type") and kw["order_type"][0].upper() == "M":
                o["order_type"] = "MARKET"
                o["status"] = "COMPLETE"
                o["average_price"] = o.get("last_price", o.get("trigger_price", 0))
                self._f.append(dict(ts=self.current_ts, ul=self.cul, order_id=oid,
                                    symbol=o["symbol"], side=o["side"], quantity=o["quantity"],
                                    average_price=o["average_price"], tag=kw.get("tag", "modify")))
            return o
        return None
    def order_cancel(self, oid):
        for o in self._o:
            if o["order_id"] == oid:
                o["status"] = "CANCELLED"
                return o
        return None
    def set_sym_tok(self, s, t):
        self._s2t[s] = t
    def sim_sl(self, lo, hi, ts):
        for o in self._o:
            if o["status"] != "TRIGGER PENDING" or not o.get("trigger_price"):
                continue
            tok = self._s2t.get(o["symbol"])
            tr = o["trigger_price"]
            if not tok:
                continue
            cp = self.p.estimate(tok, self.cul, ts)
            if cp >= tr:
                o["status"] = "COMPLETE"
                o["average_price"] = tr
                self._f.append(dict(ts=ts, ul=self.cul, order_id=o["order_id"],
                                    symbol=o["symbol"], side=o["side"],
                                    quantity=o["quantity"], average_price=tr, tag="sl_hit"))
    def find_fill(self, oid):
        for f in self._f:
            if f["order_id"] == oid:
                return float(f["average_price"])
        for o in self._o:
            if o["order_id"] == oid and o["status"] in ("COMPLETE", "FILLED"):
                return float(o["average_price"])
        return 0.0


class Restapi:
    api_object = None
    @classmethod
    def api(cls):
        return cls.api_object
    def __init__(self, broker, q=1):
        Restapi.api_object = broker
        from sdk.models import Order
        Order.set_quantity(q)
    def enter(self, kw):
        return self.api().order_place(**kw)
    def find_fillprice_from_order_id(self, oid):
        return self.api().find_fill(oid)


def run_backtest(data):
    """Run backtest on downloaded data."""
    btc_candles = data["btc_candles"]
    price_db = data["option_prices"]
    expiry = data["expiry"]

    # Build token→symbol mapping
    token_to_symbol = {}
    for sym in price_db:
        m = re.match(r'([CP])-BTC-(\d+)-' + expiry.replace("-", ""), sym)
        if m:
            strike, otype = int(m.group(2)), "CE" if m.group(1) == "C" else "PE"
            token = str(strike * 10 + (1 if otype == "CE" else 2))
            token_to_symbol[token] = sym

    pricer = Pricer(price_db, token_to_symbol)
    broker = Broker(pricer)
    ws = MockWsocket()
    symbols = MockSymbols()
    api = Restapi(broker)
    config = {"stop_loss": 150, "target": 150, "ttl": 15, "quantity": 1, "slippage": 0.5}

    om = OrderManager(ws=ws, symbols=symbols, api=api, config=config)

    # Patch get_price for new tokens
    def _bt_gp(token):
        px = ws.ltp.get(token, 0.0)
        if px == 0.0 and broker.current_ts:
            sym = token_to_symbol.get(token)
            if sym:
                px = pricer.price_at(sym, broker.current_ts)
                ws.ltp[token] = px
        return px
    om._get_price = _bt_gp

    # Patch enter_short for tracking
    _oe = om.enter_short
    def _te(ul, ot):
        r = _oe(ul, ot)
        if "error" not in r:
            broker.set_sym_tok(r["symbol"], r["token"])
            pricer.track(r["token"], r["strike"], ul, r["price"], ot, broker.current_ts)
        return r
    om.enter_short = _te

    strategy = Coinshort(config=config, symbols=symbols, api=api, om=om,
                         underlying_token=1001, underlying_symbol="BTC-USD")
    strategy.bounds = []
    strategy._entry_ce_id = None
    strategy._entry_pe_id = None
    strategy.ce = Calls()
    strategy.pe = Puts()
    strategy._satellites = []
    strategy.tier = 1
    strategy.current_premium = 0
    ws.subscribe(["1001"])

    print(f"\nRunning backtest ({len(btc_candles)} ticks)...")
    for idx, candle in enumerate(btc_candles):
        ts = candle["time"]
        close = candle["close"]
        ws.ltp["1001"] = close
        broker.cul = close
        broker.current_ts = ts

        for tok in list(ws.ltp.keys()):
            if tok != "1001":
                sym = token_to_symbol.get(tok)
                if sym:
                    ws.ltp[tok] = pricer.price_at(sym, ts)

        broker.sim_sl(candle.get("low", close), candle.get("high", close), ts)

        try:
            strategy.tick(close)
        except Exception as e:
            break

        if idx % 1440 == 0 or idx == len(btc_candles) - 1:
            dt = pendulum.from_timestamp(ts)
            print(f"  [{dt.format('MM-DD HH:mm')}] T{strategy.tier} "
                  f"CE={strategy.ce.status.name if strategy.ce.status else 'FLAT':>7} "
                  f"PE={strategy.pe.status.name if strategy.pe.status else 'FLAT':>7} "
                  f"@{close:.0f} bnd={strategy.bounds[-1] if strategy.bounds else '[]'} "
                  f"prem={strategy.current_premium:.0f} sats={len(strategy._satellites)}")

    # P&L
    net = 0
    for f in broker._f:
        q, p = int(f.get("quantity", 1)), float(f.get("average_price", 0))
        net += p * q if f.get("side") == "SELL" else -p * q

    # MTM
    last_ts = btc_candles[-1]["time"]
    mtm = 0.0
    for label, token, status in [
        ("CE", strategy.ce.instrument_token, strategy.ce.status),
        ("PE", strategy.pe.instrument_token, strategy.pe.status),
    ]:
        if status not in (LegState.SHORT, LegState.LONG, LegState.SHIFTED):
            continue
        e = pricer.entries.get(str(token))
        if not e:
            continue
        sym = token_to_symbol.get(str(token))
        curr = pricer.price_at(sym, last_ts) if sym else 0.0
        pnl = e["entry_prem"] - curr if status in (LegState.SHORT, LegState.SHIFTED) else curr - e["entry_prem"]
        mtm += pnl
    for sat in strategy._satellites:
        if sat["status"] not in (LegState.SHORT, LegState.SHIFTED):
            continue
        e = pricer.entries.get(str(sat.get("instrument_token", 0)))
        if not e:
            continue
        sym = token_to_symbol.get(str(sat.get("instrument_token", 0)))
        curr = pricer.price_at(sym, last_ts) if sym else 0.0
        mtm += e["entry_prem"] - curr

    # Save tradebook
    tradebook_path = os.path.join(DATA_DIR, "tradebook_live.csv")
    with open(tradebook_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "datetime", "underlying", "side", "symbol", "qty", "opt_price", "reason", "type"])
        for fill in broker._f:
            ts = fill.get("ts", 0)
            dt = pendulum.from_timestamp(ts).format("MM-DD HH:mm") if ts else ""
            ul = fill.get("ul", "")
            w.writerow([ts, dt, ul, fill.get("side",""), fill.get("symbol",""),
                       fill.get("quantity",1), fill.get("average_price",0),
                       fill.get("tag",""), fill.get("tag","") or "enter_short"])

    print(f"\n{'='*50}")
    print(f"LIVE BACKTEST RESULTS ({expiry}, 1m)")
    print(f"{'='*50}")
    print(f"  Expiry:     {expiry}")
    print(f"  Ticks:      {len(btc_candles)}")
    print(f"  Final tier: T{strategy.tier}")
    print(f"  CE:         {strategy.ce.status.name if strategy.ce.status else 'FLAT'}")
    print(f"  PE:         {strategy.pe.status.name if strategy.pe.status else 'FLAT'}")
    print(f"  Bounds:     {strategy.bounds[-1] if strategy.bounds else 'N/A'}")
    print(f"  Premium:    {strategy.current_premium:.0f}")
    print(f"  Fills:      {len(broker._f)}")
    print(f"  Realized:   {net:.0f}")
    print(f"  MTM:        {mtm:+.0f}")
    print(f"  Total:      {net + mtm:.0f}")
    print(f"\nTradebook: {tradebook_path}")


if __name__ == "__main__":
    print("=== Coinshort Live Backtester ===")
    print("\nDetecting monthly expiry...")
    expiry = detect_monthly_expiry()
    print(f"  Using expiry: {expiry}")
    start_dt = detect_start_date(expiry)

    data_path = os.path.join(DATA_DIR, "live_backtest_data.json")
    if os.path.exists(data_path):
        ans = input(f"  Cached data exists ({data_path}). Redownload? [y/N]: ")
        if ans.lower() != "y":
            with open(data_path) as f:
                data = json.load(f)
            print("  Using cached data")
            run_backtest(data)
            sys.exit(0)

    data = download_data(expiry, start_dt)
    run_backtest(data)

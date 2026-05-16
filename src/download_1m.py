"""
Download 1m option candles for May 29 expiry, then run backtest.
"""
import json, os, sys, time, requests, pendulum

API = "https://api.india.delta.exchange"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def fetch_candles(symbol, resolution, start, end):
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
            print(f"    Error: {e}")
        cursor = chunk
    all_c.sort(key=lambda c: c["time"])
    return all_c

def download():
    resolution = "1m"
    start_ts = int(pendulum.datetime(2026, 4, 25, tz="UTC").timestamp())
    end_ts = int(pendulum.datetime(2026, 5, 16, tz="UTC").timestamp())

    # Get option chain
    print("Fetching option chain...")
    r = requests.get(f"{API}/v2/products", params={
        "contract_types": "call_options,put_options",
        "states": "live", "expiry": "2026-05-29"
    }, timeout=15)
    opts = [p for p in r.json().get("result", [])
            if p.get("underlying_asset", {}).get("symbol") == "BTC"]
    symbols = {}
    for p in opts:
        s = p["symbol"]; strike = int(p.get("strike_price", 0))
        if 65000 <= strike <= 83000:
            symbols[s] = strike
    print(f"  {len(symbols)} ATM-range symbols")

    # Download 1m candles per symbol
    price_db = {}
    for i, (sym, strike) in enumerate(sorted(symbols.items())):
        candles = fetch_candles(sym, resolution, start_ts, end_ts)
        price_db[sym] = {c["time"]: c["close"] for c in candles}
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(symbols)} done ({len(candles)} candles for {sym})")
        time.sleep(0.1)

    # Save
    total = sum(len(v) for v in price_db.values())
    print(f"\nTotal: {len(price_db)} symbols, {total} price points")
    with open(os.path.join(DATA_DIR, "option_prices_1m_may.json"), "w") as f:
        json.dump(price_db, f)
    print("Saved to option_prices_1m_may.json")

if __name__ == "__main__":
    download()

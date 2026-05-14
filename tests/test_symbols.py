import pytest
import pandas as pd
import os
import tempfile


SAMPLE_ROWS = [
    {"exchange": "DELTA", "tradingsymbol": "BTC-28MAR25-50000-CE", "token": "1001",
     "expiry_date": "28Mar2025", "strike": 50000, "option_type": "CE", "lot_size": 1,
     "ws_token": "1001", "underlying": "BTC"},
    {"exchange": "DELTA", "tradingsymbol": "BTC-28MAR25-51000-CE", "token": "1002",
     "expiry_date": "28Mar2025", "strike": 51000, "option_type": "CE", "lot_size": 1,
     "ws_token": "1002", "underlying": "BTC"},
    {"exchange": "DELTA", "tradingsymbol": "BTC-28MAR25-49000-PE", "token": "2001",
     "expiry_date": "28Mar2025", "strike": 49000, "option_type": "PE", "lot_size": 1,
     "ws_token": "2001", "underlying": "BTC"},
    {"exchange": "DELTA", "tradingsymbol": "BTC-28MAR25-50000-PE", "token": "2002",
     "expiry_date": "28Mar2025", "strike": 50000, "option_type": "PE", "lot_size": 1,
     "ws_token": "2002", "underlying": "BTC"},
]


@pytest.fixture
def symbol_csv():
    df = pd.DataFrame(SAMPLE_ROWS)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "DELTA_BTC.csv")
        df.to_csv(path, index=False)
        yield tmp


def test_symbol_loads_from_csv(symbol_csv):
    from broker_ai.delta.symbols import Symbol
    s = Symbol(exchange="DELTA", symbol="BTC", data_path=symbol_csv)
    assert len(s.df) == 4
    assert s.diff == 1000


def test_filter_by_moneyness_ce_atm(symbol_csv):
    from broker_ai.delta.symbols import Symbol
    s = Symbol(exchange="DELTA", symbol="BTC", data_path=symbol_csv)
    rows = s.filter_by_moneyness(50500, 0, "CE")
    assert len(rows) == 1
    assert rows[0]["tradingsymbol"] == "BTC-28MAR25-50000-CE"
    assert rows[0]["ws_token"] == 1001


def test_filter_by_moneyness_pe_atm(symbol_csv):
    from broker_ai.delta.symbols import Symbol
    s = Symbol(exchange="DELTA", symbol="BTC", data_path=symbol_csv)
    rows = s.filter_by_moneyness(50500, 0, "PE")
    assert len(rows) == 1
    assert rows[0]["tradingsymbol"] == "BTC-28MAR25-50000-PE"
    assert rows[0]["ws_token"] == 2002


def test_filter_by_moneyness_ce_one_away(symbol_csv):
    from broker_ai.delta.symbols import Symbol
    s = Symbol(exchange="DELTA", symbol="BTC", data_path=symbol_csv)
    rows = s.filter_by_moneyness(50500, 1, "CE")
    assert len(rows) == 1
    assert rows[0]["strike"] == 51000


def test_filter_by_moneyness_pe_one_away(symbol_csv):
    from broker_ai.delta.symbols import Symbol
    s = Symbol(exchange="DELTA", symbol="BTC", data_path=symbol_csv)
    rows = s.filter_by_moneyness(50500, 1, "PE")
    assert len(rows) == 1
    assert rows[0]["strike"] == 49000


def test_filter_by_moneyness_empty_for_missing_strike(symbol_csv):
    from broker_ai.delta.symbols import Symbol
    s = Symbol(exchange="DELTA", symbol="BTC", data_path=symbol_csv)
    rows = s.filter_by_moneyness(50000, 10, "CE")
    assert len(rows) == 0


def test_atm_strike_calculation(symbol_csv):
    from broker_ai.delta.symbols import Symbol
    s = Symbol(exchange="DELTA", symbol="BTC", data_path=symbol_csv)
    assert s.diff == 1000
    assert s.atm_strike(49500) == 49000
    assert s.atm_strike(50500) == 50000
    assert s.atm_strike(51500) == 51000




from constants import D_SYMBOL, O_FUTL, S_DATA
import pandas as pd
from traceback import print_exc
from typing import Dict, List, Any, Union


class Symbol:
    """
    Class to get symbols from finvasia

    Parameters
    ----------
    exchange : str
        Exchange
    symbol : str
        Symbol
    expiry : str
        Expiry

    """

    def __init__(self, exchange: str, symbol: str, expiry: str):
        self.exchange = exchange
        self.symbol = symbol
        expiry = expiry

    def calc_atm_from_ltp(self, ltp) -> int:
        current_strike = ltp - (ltp % dct_sym[self.symbol]["diff"])
        next_higher_strike = current_strike + dct_sym[self.symbol]["diff"]
        if ltp - current_strike < next_higher_strike - ltp:
            return int(current_strike)
        return int(next_higher_strike)


def get_symbols(exchange: str) -> Dict[str, Dict[str, Any]]:
    try:
        info = {}
        url = f"https://api.kite.trade/instruments/{exchange}"
        df = pd.read_csv(url)
        # keep only tradingsymbol and instrument_token
        df = df[["tradingsymbol", "instrument_token"]]
        info = df.to_dict(orient="records")
        # flatten list in dictionary values
        info = {exchange: items for items in info}
    except Exception as e:
        print(e)
        print_exc()
    finally:
        return info


def dump():
    sym_from_yml = O_FUTL.get_lst_fm_yml(S_DATA + "symbols.yml")
    dump_file = S_DATA + "symbols.json"
    if O_FUTL.is_file_not_2day(dump_file):
        exchanges = sym_from_yml.pop("exchanges", None)
        for exchange in exchanges:
            sym_from_yml.update(get_symbols(exchange))
        O_FUTL.write_file(S_DATA + "symbols.json", sym_from_yml)


def dict_from_yml(index_exchange, key_to_search, value_to_match):
    try:
        sym_from_yml = O_FUTL.get_lst_fm_yml(S_DATA + "symbols.yml")
        dct = [
            d
            for k, d in sym_from_yml.items()
            if k == index_exchange and d[key_to_search] == value_to_match
        ][0]
        print(f"{dct=}")
        return dct
    except Exception as e:
        print(e)
        print_exc()


def tokens_from_symbols(symbols: List[str]) -> List[str]:
    try:
        symbols_from_json = O_FUTL.read_file(S_DATA + "symbols.json")
        bn_from_json = [
            dct
            for k, dct in symbols_from_json.items()
            if k == "NFO" and dct["tradingsymbol"].startswith("BANKNIFTY")
        ]
        print(bn_from_json)
        """
        filter = [
            item for item in symbols_from_json if item["tradingsymbol"] in symbols
        ]
        print(filter)
        """
        return symbols_from_json
    except Exception as e:
        print(e)


def build_chain(index_exchange, base, expiry):
    try:
        dct = dict_from_yml(index_exchange, "base", base)
        atm = 46000
        lst = []
        lst.append(base + expiry + str(atm) + "CE")
        lst.append(base + expiry + str(atm) + "PE")
        for v in range(1, dct["depth"]):
            lst.append(base + expiry + str(atm + v * dct["diff"]) + "CE")
            lst.append(base + expiry + str(atm + v * dct["diff"]) + "PE")
            lst.append(base + expiry + str(atm - v * dct["diff"]) + "CE")
            lst.append(base + expiry + str(atm - v * dct["diff"]) + "PE")
        filter = tokens_from_symbols(lst)
        return filter
    except Exception as e:
        print(f"build chain error: {e}")
        print_exc()
        SystemExit(1)

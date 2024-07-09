from constants import O_FUTL, S_DATA
import pandas as pd
from traceback import print_exc
from typing import Dict, List, Any


def calc_atm_from_ltp(ltp) -> int:
    current_strike = ltp - (ltp % dct_sym[self.symbol]["diff"])
    next_higher_strike = current_strike + dct_sym[self.symbol]["diff"]
    if ltp - current_strike < next_higher_strike - ltp:
        return int(current_strike)
    return int(next_higher_strike)


def get_symbols(exchange: str) -> Dict[str, Dict[str, Any]]:
    try:
        json = {}
        url = f"https://api.kite.trade/instruments/{exchange}"
        df = pd.read_csv(url)
        # keep only tradingsymbol and instrument_token
        df = df[["tradingsymbol", "instrument_token"]]
        json = df.to_dict(orient="records")
        # flatten list in dictionary values
    except Exception as e:
        print(e)
        print_exc()
    finally:
        return json


def dump():
    # what exchange and its symbols should be dumped
    sym_from_yml = O_FUTL.get_lst_fm_yml(S_DATA + "symbols.yml")
    exchanges = sym_from_yml.pop("exchanges", None)
    # iterate each exchange
    for exchange in exchanges:
        exchange_file = S_DATA + exchange + ".json"
        if O_FUTL.is_file_not_2day(exchange_file):
            sym_from_json = get_symbols(exchange)
            O_FUTL.write_file(exchange_file, sym_from_json)


def dict_from_yml(key_to_search, value_to_match):
    try:
        dct = {}
        sym_from_yml = O_FUTL.get_lst_fm_yml(S_DATA + "symbols.yml")
        for _, dct in sym_from_yml.items():
            if isinstance(dct, dict) and dct[key_to_search] == value_to_match:
                return dct
        print(f"{dct=}")
        return dct
    except Exception as e:
        print(e)
        print_exc()


def tokens_from_symbols(symbols: List[str], info: Dict) -> List[str]:
    try:
        filter = []
        exchange = info["exchange"]
        symbols_from_json = O_FUTL.read_file(S_DATA + exchange + ".json")
        for symtoken in symbols_from_json:
            if (
                symtoken["tradingsymbol"].startswith(info["base"])
                and symtoken["tradingsymbol"] in symbols
            ):
                filter.append(symtoken)
        return filter
    except Exception as e:
        print(e)


def build_chain(base, expiry):
    try:
        dct = dict_from_yml("base", base)
        atm = 46000
        lst = []
        lst.append(base + expiry + str(atm) + "CE")
        lst.append(base + expiry + str(atm) + "PE")
        for v in range(1, dct["depth"]):
            lst.append(base + expiry + str(atm + v * dct["diff"]) + "CE")
            lst.append(base + expiry + str(atm + v * dct["diff"]) + "PE")
            lst.append(base + expiry + str(atm - v * dct["diff"]) + "CE")
            lst.append(base + expiry + str(atm - v * dct["diff"]) + "PE")
        filter = tokens_from_symbols(lst, dct)
        return filter
    except Exception as e:
        print(f"build chain error: {e}")
        print_exc()
        SystemExit(1)

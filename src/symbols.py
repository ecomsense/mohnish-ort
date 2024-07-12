from constants import O_FUTL, S_DATA
import pandas as pd
from traceback import print_exc
from typing import Dict, List, Any


def get_symbols(exchange: str) -> Dict[str, Dict[str, Any]]:
    try:
        json = {}
        url = f"https://api.kite.trade/instruments/{exchange}"
        df = pd.read_csv(url)
        # keep only tradingsymbol and instrument_token
        df = df[["tradingsymbol", "instrument_token", "name", "strike", "instrument_type", "expiry", "lot_size"]]
        json = df.to_dict(orient="records")
        # flatten list in dictionary values
    except Exception as e:
        print(e)
        print_exc()
    finally:
        return json


def dump():
    try:
        # what exchange and its symbols should be dumped
        sym_from_yml = O_FUTL.get_lst_fm_yml(S_DATA + "symbols.yml")
        exchanges = sym_from_yml.pop("exchanges", None)
        # iterate each exchange
        for exchange in exchanges:
            exchange_file = S_DATA + exchange + ".json"
            if O_FUTL.is_file_not_2day(exchange_file):
                sym_from_json = get_symbols(exchange)
                O_FUTL.write_file(exchange_file, sym_from_json)
    except Exception as e:
        print(f"dump error: {e}")
        print_exc()


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
        print(f"dict from yml error: {e}")
        print_exc()


class Symbols:
    def __init__(self, **kwargs):
        if any(kwargs):
            # create property from dictionary
            for key, value in kwargs.items():
                setattr(self, key, value)

    def calc_atm_from_ltp(self, ltp) -> int:
        try:
            current_strike = ltp - (ltp % self.diff)
            next_higher_strike = current_strike + self.diff
            if ltp - current_strike < next_higher_strike - ltp:
                return int(current_strike)
            return int(next_higher_strike)
        except Exception as e:
            print(f"calc atm error: {e}")
            print_exc()

    def tokens_from_symbols(self, symbols: List[str]) -> List:
        try:
            filter = []
            exchange = self.exchange  # pyright: ignore
            symbols_from_json = O_FUTL.read_file(S_DATA + exchange + ".json")
            for symtoken in symbols_from_json:
                if (
                    symtoken["tradingsymbol"].startswith(self.base)
                    and symtoken["tradingsymbol"] in symbols
                ):
                    filter.append(symtoken)
            return filter
        except Exception as e:
            print(f"tokens from symbols error: {e}")
            print_exc()

    def build_chain(self, expiry, ltp, full_chain=True):
        try:
            atm = self.calc_atm_from_ltp(ltp)
            depth = self.depth if full_chain else 0
            symbols = self._generate_symbols(expiry, atm, depth)
            print(f"Symbols: {symbols}")
            filter = self.tokens_from_symbols(symbols)
            return filter
        except Exception as e:
            print(f"generate_symbols error: {e}")
            print_exc()
    
    def _generate_symbols(self, expiry, atm, depth):
        lst = [self.base + expiry + str(atm) + opt for opt in ["CE", "PE"]]
        if depth > 0:
            lst.extend(self.base + expiry + str(atm + v * self.diff) + opt for v in range(1, depth + 1) for opt in ["CE", "PE"])
            lst.extend(self.base + expiry + str(atm - v * self.diff) + opt for v in range(1, depth + 1) for opt in ["CE", "PE"])
        print(f"in _gen lst is {lst}")
        return lst

    def get_straddle(self, expiry, ltp):
        try:
            return self.build_chain(expiry, ltp, full_chain=False)
        except Exception as e:
            print(f"get_straddle error: {e}")
            print_exc()
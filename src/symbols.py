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
        self.expiry = expiry

    def build_chain(self, args: Union[List[str], int]):
        """
        finds token from data dir csv dump
        parameter:
            input: list of exchange:symbols or atm as integer
            output: dictionary with symbol key and token as value
        """
        try:
            df = pd.read_csv(self.csvfile)
            lst = []
            if isinstance(args, list):
                for args in args:
                    exch = args.split(":")[0]
                    sym = args.split(":")[1]
                    if exch == self.exchange:
                        lst.append(sym)
            elif isinstance(args, int):
                lst.append(self.symbol + self.expiry + str(args) + "CE")
                lst.append(self.symbol + self.expiry + str(args) + "PE")
                for v in range(1, dct_sym[self.symbol]["depth"]):
                    lst.append(
                        self.symbol
                        + self.expiry
                        + str(args + v * dct_sym[self.symbol]["diff"])
                        + "CE"
                    )
                    lst.append(
                        self.symbol
                        + self.expiry
                        + str(args + v * dct_sym[self.symbol]["diff"])
                        + "PE"
                    )
                    lst.append(
                        self.symbol
                        + self.expiry
                        + str(args - v * dct_sym[self.symbol]["diff"])
                        + "CE"
                    )
                    lst.append(
                        self.symbol
                        + self.expiry
                        + str(args - v * dct_sym[self.symbol]["diff"])
                        + "PE"
                    )
            else:
                raise ValueError(f"str({args}) must be list or int")
            df = df[df["tradingsymbol"].isin(lst)]
            return dict(zip(df["tradingsymbol"], df["instrument_token"]))
        except Exception as e:
            print(f"find_token_from_dump: {e}")
            print_exc()
            SystemExit(1)

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
        df = df[["tradingsymbol", "instrument_token"]].rename(
            columns={"tradingsymbol": "symbol", "instrument_token": "token"}
        )
        info = df.to_dict(orient="records")
        # flatten list in dictionary values
        info = {exchange: items for items in info}
    except Exception as e:
        print(e)
        print_exc()
    finally:
        return info


def dump():
    dump_file = S_DATA + "symbols.json"
    if O_FUTL.is_file_not_2day(dump_file):
        exchanges = D_SYMBOL.pop("exchanges", None)
        for exchange in exchanges:
            D_SYMBOL.update(get_symbols(exchange))

    O_FUTL.write_file(S_DATA + "symbols.json", D_SYMBOL)
    return D_SYMBOL

from pprint import pprint
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
from constants import O_FUTL, S_DATA
from sdk.symbol import OptionSymbol

F_SIGNAL = S_DATA + "signals.csv"

def _read_xls():
    df = pd.read_csv(F_SIGNAL)
    if not df.empty: 
        df = df.where(pd.notnull(df), None)
        sr_columns = df.columns[1:]
        df["sr"] = df[sr_columns].apply(
            lambda row: [val for val in row if val is not None], axis=1
        )
        return df[["tradingsymbol", "sr"]].to_dict(orient="records")
    return []

def read_supp_and_res(logging, **kwargs):
    try: 
        srs = []
        if O_FUTL.is_file_exists(F_SIGNAL):
            srs = _read_xls()
        if any(srs):
            pprint(srs)
            sym_helper = OptionSymbol(**kwargs)
            for sr in srs:
                tokens = sym_helper.tokens_from_symbols(sr["tradingsymbol"])
                if tokens:
                    sr["instrument_token"] = tokens[0]["instrument_token"]
        return srs
    except Exception as e:
        logging.warning(f"{e} reading srs")
        return []

def pfx_and_sfx(lst_of_dct: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for d in lst_of_dct:
        lst = d["sr"]
        new_list = [0]
        new_list.extend(lst)
        new_list.extend([sum(lst)])
        new_list.sort()
        d["sr"] = new_list
    return lst_of_dct

def unify_dict(
    support_resistance: List[Dict[str, Any]],
    prices: List[Dict[str, Any]],
    key_to_match: str,
) -> List[Dict[str, Any]]:
    for d in support_resistance:
        for p in prices:
            if d[key_to_match] == p[key_to_match]:
                d.update(p)
    return support_resistance

def _find_band(lst: List[Tuple], V: float) -> Tuple[float, float]:
    arr = np.array(lst)
    idx = np.searchsorted(arr, V)
    if idx == 0:
        return arr[0], arr[1]
    elif idx == len(arr):
        return arr[-2], arr[-1]
    lower_bound = arr[idx - 1]
    upper_bound = arr[idx]
    if lower_bound == upper_bound:
        if idx > 1:
            lower_bound = arr[idx - 2]
        elif idx < len(arr) - 1:
            upper_bound = arr[idx + 1]
    return lower_bound, upper_bound

def check_any_out_of_bounds_np(lists_to_check: Tuple) -> bool:
    bounds, values = lists_to_check
    bounds = np.array(bounds)
    values = np.array(values)
    lower_bounds = bounds[:, 0]
    upper_bounds = bounds[:, 1]
    lower_out_of_bounds = values < lower_bounds
    upper_out_of_bounds = values > upper_bounds
    return np.any(lower_out_of_bounds | upper_out_of_bounds)

def find_band(lst: List[Dict[str, Any]]) -> Tuple[List[Tuple], List[float]]:
    for d in lst:
        d["band"] = _find_band(d["sr"], d["last_price"])
    lst_of_bands: List[Tuple] = [d["band"] for d in lst]
    lst_of_prices: List[float] = [d["last_price"] for d in lst]
    return lst_of_bands, lst_of_prices

from pprint import pprint
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from constants import O_FUTL, S_DATA
from symbols import Symbols

F_SIGNAL = S_DATA + "signals.csv"


def _read_xls():
    df = pd.read_csv(F_SIGNAL)
    df = df.where(pd.notnull(df), None)
    sr_columns = df.columns[1:]
    df["sr"] = df[sr_columns].apply(
        lambda row: [val for val in row if val is not None], axis=1
    )
    result_df = df[["tradingsymbol", "sr"]]
    srs = result_df.to_dict(orient="records")
    return srs


def read_supp_and_res():
    srs = []
    if O_FUTL.is_file_exists(F_SIGNAL):
        srs = _read_xls()
    """
    srs = [
        {"tradingsymbol": "HDFCBANK", "sr": [1600, 1650, 1699, 1725, 1775, 1900]},
        {"tradingsymbol": "ICICIBANK", "sr": [1000, 1100, 1200, 1300, 1500, 1550]},
    ]
    """
    pprint(srs)
    if any(srs):
        kwargs = {"exchange": "BSE"}
        nse_symbols = Symbols(**kwargs)
        for sr in srs:
            sr["instrument_token"] = nse_symbols.tokens_from_symbols(
                sr["tradingsymbol"]
            )[0]["instrument_token"]
    return srs


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
    # merge dictionary of lists based on instrument_token as key
    for d in support_resistance:
        for p in prices:
            if d[key_to_match] == p[key_to_match]:
                d.update(p)
    return support_resistance


def _find_band(lst: List[Tuple], V: float) -> Tuple[float, float]:
    arr = np.array(lst)

    # Find the index where V would be inserted to maintain order
    idx = np.searchsorted(arr, V)

    # Handle cases where V is exactly at the lower or upper bounds of the array
    if idx == 0:
        return arr[0], arr[1]
    elif idx == len(arr):
        return arr[-2], arr[-1]

    # Check for exact match or finding appropriate bounds
    lower_bound = arr[idx - 1]
    upper_bound = arr[idx]

    # Ensure the bounds are not the same
    if lower_bound == upper_bound:
        if idx > 1:
            lower_bound = arr[idx - 2]
        elif idx < len(arr) - 1:
            upper_bound = arr[idx + 1]

    return lower_bound, upper_bound


def check_any_out_of_bounds_np(lists_to_check: Tuple) -> bool:
    """
    Check if any value is out of bounds using NumPy arrays for efficiency.

    :param bounds: A list of tuples, where each tuple contains (lower, upper).
    :param values: A list of values to check against the bounds.
    :return: True if any value is out of bounds, False otherwise.
    """
    bounds, values = lists_to_check
    # Convert bounds and values to NumPy arrays
    bounds = np.array(bounds)
    values = np.array(values)

    # Extract lower and upper bounds
    lower_bounds = bounds[:, 0]
    upper_bounds = bounds[:, 1]

    lower_out_of_bounds = values < lower_bounds
    upper_out_of_bounds = values > upper_bounds

    # Check if any value is out of bounds
    any_out_of_bounds = np.any(lower_out_of_bounds | upper_out_of_bounds)

    return any_out_of_bounds


def find_band(lst: List[Dict[str, Any]]) -> Tuple[List[Tuple], List[float]]:
    # find bands
    for d in lst:
        d["band"] = _find_band(d["sr"], d["last_price"])
    pprint(lst)

    lst_of_bands: List[Tuple] = [d["band"] for d in lst]
    lst_of_prices: List[float] = [d["last_price"] for d in lst]
    return lst_of_bands, lst_of_prices


if __name__ == "__main__":
    support_resistance = [
        {"instrument_token": "HDFCBANK", "sr": [1, 25, 30]},
        {"instrument_token": "AXISBANK", "sr": [1, 200, 3500]},
        {"instrument_token": "ICICIBANK", "sr": [1, 25, 30]},
    ]

    prices = [
        {"instrument_token": "HDFCBANK", "last_price": 28},
        {"instrument_token": "AXISBANK", "last_price": 3500},
        {"instrument_token": "ICICIBANK", "last_price": 25},
        {"instrument_token": "NOSTOCK", "last_price": 25},
    ]

    # do in place replacement on sr values after adding sfx and pfx
    support_resistance = pfx_and_sfx(support_resistance)

    # update last price for each dictionary
    lst = unify_dict(support_resistance, prices, "instrument_token")

    lst_of_bands, lst_of_prices = find_band(lst)

    lst_of_bands.append((0, 1))
    lst_of_prices.append(3)
    print(lst_of_bands, lst_of_prices)
    lists_to_check = lst_of_bands, lst_of_prices
    print(check_any_out_of_bounds_np(lists_to_check))
if __name__ == "__main__":
    print(read_supp_and_res())

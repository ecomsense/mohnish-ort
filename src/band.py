from pprint import pprint

import numpy as np


def make_array(lst_of_dct):
    for d in lst_of_dct:
        lst = d["sr"]
        new_list = [0]
        new_list.extend(lst)
        new_list.extend([sum(lst)])
        new_list.sort()
        d["sr"] = new_list
    return lst_of_dct


def extend_dict(support_resistance, prices, key_to_match):
    # merge dictionary of lists based on tradingsymbol as key
    for d in support_resistance:
        for p in prices:
            if d[key_to_match] == p[key_to_match]:
                d.update(p)
    return support_resistance


def find_bounds(lst, V):
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


def check_any_out_of_bounds_np(bounds: list, values: list):
    """
    Check if any value is out of bounds using NumPy arrays for efficiency.

    :param bounds: A list of tuples, where each tuple contains (lower, upper).
    :param values: A list of values to check against the bounds.
    :return: True if any value is out of bounds, False otherwise.
    """
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


def is_signal(support_resistance, prices):
    # do in place replacement on sr values after adding sfx and pfx
    support_resistance = make_array(support_resistance)

    # update last price for each dictionary
    lst = extend_dict(support_resistance, prices, "tradingsymbol")

    # find bands
    for d in lst:
        d["band"] = find_bounds(d["sr"], d["last_price"])
    pprint(lst)

    lst_of_bands = [d["band"] for d in lst]
    lst_of_prices = [d["last_price"] for d in lst]
    any_out_of_bounds = check_any_out_of_bounds_np(lst_of_bands, lst_of_prices)
    return any_out_of_bounds


if __name__ == "__main__":
    support_resistance = [
        {"tradingsymbol": "HDFCBANK", "sr": [1, 25, 30]},
        {"tradingsymbol": "AXISBANK", "sr": [1, 200, 3500]},
        {"tradingsymbol": "ICICIBANK", "sr": [1, 25, 30]},
    ]

    prices = [
        {"tradingsymbol": "HDFCBANK", "last_price": 28, "instrument_token": 1},
        {"tradingsymbol": "AXISBANK", "last_price": 3500, "instrument_token": 2},
        {"tradingsymbol": "ICICIBANK", "last_price": 25, "instrument_token": 3},
        {"tradingsymbol": "NOSTOCK", "last_price": 25, "instrument_token": 3},
    ]

    print(is_signal(support_resistance, prices))

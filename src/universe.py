from symbols import Symbols


def read_supp_and_res():
    srs = [
        {"tradingsymbol": "HDFCBANK", "sr": [1600, 1650, 1699, 1725, 1775, 1900]},
        {"tradingsymbol": "ICICIBANK", "sr": [1000, 1100, 1200, 1300, 1500, 1550]},
    ]
    kwargs = {"exchange": "NSE"}
    nse_symbols = Symbols(**kwargs)
    for sr in srs:
        sr["instrument_token"] = nse_symbols.tokens_from_symbols(sr["tradingsymbol"])[
            0
        ]["instrument_token"]
    return srs

import pandas as pd

from constants import O_FUTL, S_DATA, logging
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
    print(srs)
    if any(srs):
        kwargs = {"exchange": "NSE"}
        nse_symbols = Symbols(**kwargs)
        for sr in srs:
            sr["instrument_token"] = nse_symbols.tokens_from_symbols(
                sr["tradingsymbol"]
            )[0]["instrument_token"]
            print(sr["instrument_token"])
    return srs


if __name__ == "__main__":
    print(read_supp_and_res())

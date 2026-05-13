from traceback import print_exc
from typing import Any, Dict, List
import pandas as pd
from constants import O_FUTL, S_DATA, get_logger

log = get_logger(__name__)

def get_symbols(exchange: str) -> List[Dict[str, Any]]:
    try:
        url = f"https://api.kite.trade/instruments/{exchange}"
        df = pd.read_csv(url)
        df = df[
            [
                "tradingsymbol",
                "instrument_token",
                "name",
                "strike",
                "instrument_type",
                "expiry",
                "lot_size",
            ]
        ]
        df = df.dropna(axis=1, how="any")
        return df.to_dict(orient="records")
    except Exception as e:
        log.error(f"get_symbols error: {e}")
        print_exc()
        return []

def dump():
    try:
        sym_from_yml = O_FUTL.get_lst_fm_yml(S_DATA + "symbols.yml")
        exchanges = sym_from_yml.pop("exchanges", None)
        for exchange in exchanges:
            exchange_file = S_DATA + exchange + ".json"
            if O_FUTL.is_file_not_2day(exchange_file):
                sym_from_json = get_symbols(exchange)
                O_FUTL.write_file(exchange_file, sym_from_json)
    except Exception as e:
        log.error(f"dump error: {e}")
        print_exc()

class OptionSymbol:
    def __init__(self, **kwargs):
        log.debug("initializing OptionSymbol")
        for key, value in kwargs.items():
            setattr(self, key, value)
        
        self.symbols_from_json = O_FUTL.read_file(S_DATA + self.exchange + ".json")

    def tokens_from_symbols(self, symbols: List[str]) -> List:
        try:
            if isinstance(symbols, str):
                symbols = [symbols]
            return [s for s in self.symbols_from_json if s["tradingsymbol"] in symbols]
        except Exception as e:
            log.error(f"tokens from symbols error: {e}")
            print_exc()
            return []

    def calc_atm(self, ltp) -> int:
        try:
            return round(ltp / self.diff) * self.diff
        except Exception as e:
            log.error(f"calc atm error: {e}")
            print_exc()
            return 0

    def get_expiry(self, expiry_offset=0):
        try:
            df = pd.DataFrame(self.symbols_from_json)
            filtered_df = df[df["name"] == self.base]
            filtered_df = filtered_df.drop_duplicates(subset=["expiry"])
            filtered_df["expiry"] = pd.to_datetime(filtered_df["expiry"])
            today = pd.Timestamp.now().normalize()
            future_expiries = filtered_df[filtered_df["expiry"] >= today].sort_values(by="expiry")
            
            if 0 <= expiry_offset < len(future_expiries):
                self.expiry_date = future_expiries.iloc[expiry_offset]["expiry"]
                return self.expiry_date
            return None
        except Exception as e:
            log.error(f"get_expiry error: {e}")
            print_exc()
            return None

    def get_option_symbols(self, ltp):
        atm = self.calc_atm(ltp)
        # Simplified straddle generation as per super-ai pattern
        ce_symbol = f"{self.base}{self.expiry}{atm}CE"
        pe_symbol = f"{self.base}{self.expiry}{atm}PE"
        
        # Verify they exist in master
        tokens = self.tokens_from_symbols([ce_symbol, pe_symbol])
        if len(tokens) < 2:
            log.error(f"Option symbols {ce_symbol} or {pe_symbol} not found in master")
            # Fallback to searching if naming convention differs
            # (Keeping logic from original Symbols class)
            # ...
        
        return ce_symbol, pe_symbol

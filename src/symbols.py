from datetime import datetime
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

        df = df.dropna(axis=1, how='any')
        json = df.to_dict(orient="records")

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
        self.symbols_from_json = O_FUTL.read_file(S_DATA + self.exchange + ".json")

    def calc_atm_from_ltp(self, ltp) -> int:
        try:
            return round(ltp / self.diff) * self.diff
        except Exception as e:
            print(f"calc atm error: {e}")
            print_exc()

    def _generate_symbols(self, atm, depth):
        """
        Generate a list of option symbols based on the given ATM (At the Money) price and depth.

        Parameters:
        atm (int): The At the Money price for the base instrument.
        depth (int): The number of strikes above and below the ATM price to include in the build chain.

        Returns:
        list: A list of option symbols (tradingsymbols) for the specified ATM and depth.
        """
        # Filter by the base, expiry
        df = pd.DataFrame(self.symbols_from_json)
        df['expiry'] = pd.to_datetime(df['expiry'])
        filtered_df = df[(df['name'] == self.base) & (df['expiry'] == self.expiry_date)]

        merged_list = []

        for option_type in ['CE', 'PE']:
            option_df = filtered_df[filtered_df['instrument_type'] == option_type]

            # Sort DataFrame by strike
            option_df = option_df.sort_values(by='strike')

            # Find the index of the closest strike to the base strike
            closest_index = option_df.index[(option_df['strike'] - atm).abs().argsort()[:1]].tolist()

            if not closest_index:
                continue  # Skip if no closest strike found

            closest_index = closest_index[0]

            # Get the sorted strikes
            strikes = option_df['strike'].tolist()

            # Find the position of the base strike in the sorted list
            base_position = strikes.index(option_df.loc[closest_index, 'strike'])

            # Calculate the range for the depth
            start_index = max(base_position - depth, 0)
            end_index = min(base_position + depth + 1, len(strikes))

            # Filter rows within the depth range
            depth_filtered_df = option_df.iloc[start_index:end_index]
            merged_list.append(depth_filtered_df.iloc[0]['tradingsymbol'])

        print(f"Merged Build chain {merged_list}")
        return merged_list

    def tokens_from_symbols(self, symbols: List[str]) -> List:
        try:
            filter = []
            for symtoken in self.symbols_from_json:
                if (
                    # symtoken["tradingsymbol"].startswith(self.base) and
                    symtoken["tradingsymbol"] in symbols
                ):
                    filter.append(symtoken)
            return filter
        except Exception as e:
            print(f"tokens from symbols error: {e}")
            print_exc()

    def build_chain(self, ltp, full_chain=True):
        try:
            atm = self.calc_atm_from_ltp(ltp)
            print(f"ATM {atm}")
            depth = self.depth if full_chain else 0
            symbols = self._generate_symbols(atm, depth)
            print(f"Symbols: {symbols}")
            filter = self.tokens_from_symbols(symbols)
            return filter
        except Exception as e:
            print(f"generate_symbols error: {e}")
            print_exc()

    def get_straddle(self, ltp):
        try:
            return self.build_chain(ltp, full_chain=False)
        except Exception as e:
            print(f"get_straddle error: {e}")
            print_exc()

    
    def get_expiry(self, expiry_offset=0):
        """
        Get the expiry date for the specified base instrument with an optional expiry offset.

        Parameters:
        expiry_offset (int, optional): The offset from the current date to the desired expiry date. Defaults to 0.

        Returns:
        pd.Timestamp or None: The expiry date if found, otherwise None.
        """
        try:
            # Create DataFrame and filter by name
            df = pd.DataFrame(self.symbols_from_json)
            filtered_df = df[df['name'] == self.base]
            
            # Drop duplicates, convert expiry to datetime, and filter future expiries
            filtered_df = filtered_df.drop_duplicates(subset=['expiry'])
            filtered_df['expiry'] = pd.to_datetime(filtered_df['expiry'])
            today = pd.Timestamp.now().normalize()
            future_expiries = filtered_df[filtered_df['expiry'] >= today]

            # Sort and check offset
            future_expiries = future_expiries.sort_values(by='expiry')
            if 0 <= expiry_offset < len(future_expiries):
                expiry_date = future_expiries.iloc[expiry_offset]['expiry']
                self.expiry_date = expiry_date
                print(f"Expiry date with offset {expiry_offset} for {self.base}: {expiry_date}")
                return expiry_date
            return None
        except Exception as e:
            print(f"get_straddle error: {e}")
            print_exc()

    def get_option_symbols(self, ltp):
        straddle = self.get_straddle(ltp)
        print(f"Straddle {straddle}")

        # Use dictionary comprehension to map instrument types to their symbols
        symbols = {item['instrument_type']: item['tradingsymbol'] for item in straddle}

        # Extract the symbols for CE and PE
        ce_symbol = symbols.get('CE')
        pe_symbol = symbols.get('PE')

        print(f"CE symbol: {ce_symbol}, PE symbol: {pe_symbol}")
        return ce_symbol, pe_symbol

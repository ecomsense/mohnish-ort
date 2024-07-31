from traceback import print_exc

from toolkit.kokoo import is_time_past, timer

from api import Helper
from band import check_any_out_of_bounds_np, find_band, pfx_and_sfx, unify_dict
from constants import O_SETG, logging
from options import Calls, Puts
from symbols import Symbols, dict_from_yml, dump
from universe import read_supp_and_res
from wsocket import Wsocket


class TradingStrategy:
    def __init__(self, settings, symbol_settings):
        self.symbols = Symbols(**symbol_settings)
        self.quantity = settings["quantity"]
        self.stop_loss = settings["stop_loss"]
        self.expiry_offset = settings.get("expiry_offset", 1)
        # self.expiry = self.symbols.get_expiry(expiry_offset=self.expiry_offset)
        self.help = Helper(settings["quantity"])
        self.ce = Calls()
        self.pe = Puts()
        support_resistance = read_supp_and_res()
        # do in place replacement on sr values after adding sfx and pfx
        self.sr = pfx_and_sfx(support_resistance)

        logging.debug("subscribing index from symbols yml automtically")
        self.ws: object = Wsocket()
        self.quotes = False
        while not self.quotes or not any(self.quotes):
            self.quotes = self.ws.ltp()

        logging.debug("decipher ltp from websocket response")
        # TODO merge expiry offset

        # build option chain
        bn_ltp = self.ltp_from_ws_response(self.symbols.instrument_token)
        tokens = self.symbols.build_chain(bn_ltp, full_chain=True)
        self.quotes = self.ws.ltp(tokens)

        # subscribe to support and resistance
        # sr_tokens = [dct["instrument_token"] for dct in self.sr]
        self.quotes = self.ws.ltp(self.sr)

    def ltp_from_ws_response(self, instrument_token):
        try:
            logging.debug(f"incoming token({instrument_token})")
            self.quotes = self.ws.ltp()
            last_price = [
                d["last_price"]
                for d in self.quotes
                if d["instrument_token"] == instrument_token
            ][0]
            if last_price is None:
                raise Exception("price is None")
            return last_price
        except Exception as e:
            print(f"ltp error: {e}")
            print_exc()

    def short(self, option):
        try:
            bn_ltp = None
            while bn_ltp is None:
                bn_ltp = self.ltp_from_ws_response(self.symbols.instrument_token)
                logging.debug("WAITING FOR UNDERLYING LTP")
            ce_symbol, pe_symbol = self.symbols.get_option_symbols(bn_ltp)
            option.tradingsymbol = ce_symbol if isinstance(option, Calls) else pe_symbol
            option.instrument_token = self.symbols.tokens_from_symbols(
                option.tradingsymbol
            )[0]["instrument_token"]
            logging.debug(f"{option.tradingsymbol} / {option.instrument_token})")
            last_price = None
            while last_price is None:
                last_price = self.ltp_from_ws_response(option.instrument_token)
                logging.debug("WAITING FOR OPTIONS LTP")
            params = {
                "symbol": option.tradingsymbol,
                "side": "SELL",
                "order_type": "MARKET",
                "last_price": last_price,
            }
            logging.debug(f"enter params: {params}")
            option.short_id = self.help.enter(params)
            logging.info(f"short_id: {option.short_id}")
            option.short_params = params

            params["side"] = "BUY"
            params["order_type"] = "SL"
            params["quantity"] = self.quantity * 2
            params["trigger_price"] = params["last_price"] + self.stop_loss
            params["tag"] = "stoploss"
            option.buy_id = self.help.enter(params)
            logging.info(f"buy_id: {option.buy_id}")
            option.buy_params = params
        except Exception as e:
            logging.error(f"short error: {e}")
            print_exc()

    def is_order_complete(self, subset):
        try:

            def is_subset(S, H):
                """
                Check if dictionary S is a subset of dictionary H.

                Args:
                    S (dict): The subset dictionary.
                    H (dict): The superset dictionary.

                Returns:
                    bool: True if S is a subset of H, False otherwise.
                """
                for key, value in S.items():
                    if key not in H or H[key] != value:
                        return False
                return True

            flag = False
            for dct in self.orders:
                if is_subset(subset, dct):
                    flag = True
                    break
        except Exception as e:
            logging.info(f" is_order_complete error: {e}")
        finally:
            return flag

    def set_bounds_to_check(self, opt):
        # update last price for each dictionary
        lst = unify_dict(self.sr, self.quotes, "instrument_token")
        lst_of_bands, lst_of_prices = find_band(lst)
        median = opt.buy_params["last_price"]
        lst_of_bands.append((median - self.stop_loss, median + self.stop_loss))
        lst_of_prices.append(median)
        print("setting bounds", lst_of_bands, lst_of_prices)
        self.bounds = lst_of_bands, lst_of_prices

    def is_price_above(self, option):
        current_price = None
        while current_price is None:
            current_price = self.ltp_from_ws_response(option.instrument_token)
        if current_price > option.buy_params["trigger_price"]:
            return True
        return False

    def run(self):
        try:
            while True:
                self.orders = self.help.api().orders
                self.quotes = self.ws.ltp()
                lst = [self.ce, self.pe]
                for opt in lst:
                    if opt.status == -1:
                        subset = {"order_id": opt.buy_id, "status": "COMPLETE"}
                        if self.is_order_complete(subset):
                            opt.status = 1
                        elif self.is_price_above(opt):
                            opt.buy_params["order_id"] = opt.buy_id
                            opt.buy_params["order_type"] = "MARKET"
                            self.help.api().order_modify(**opt.buy_params)
                            opt.status = 1
                        ## status is a fresh buy
                        if opt.status == 1:
                            self.set_bounds_to_check(opt)
                    elif opt.status == 1:
                        print(self.bounds)
                        if check_any_out_of_bounds_np(self.bounds):
                            # sell existing position
                            self.help.exit(opt.buy_params)
                            opt.status = 0
                    elif opt.status == 0:
                        # short new position
                        self.short(opt)
                        opt.status = -1
                print(vars(self.ce))
                print(vars(self.pe))
                timer(1)
        except Exception as e:
            print(f"run error: {e}")
            print_exc()


def root():
    try:
        logging.info("HAPPY TRADING")
        # download necessary masters
        dump()
        entry_time: str = O_SETG["program"]["start"]
        strategy_settings = O_SETG["strategy"]
        # Unpack settings into instance attributes
        symbol_settings = dict_from_yml("base", "BANKNIFTY")
        while not is_time_past(entry_time):
            logging.info(f"z #@! zZZ sleeping till {entry_time}")
            timer(1)
        TradingStrategy(strategy_settings, symbol_settings).run()
    except Exception as e:
        print(f"root error: {e}")
        print_exc()


root()

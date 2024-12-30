from os import name
from api import Helper
from models import Calls, Puts
from signals import (
    check_any_out_of_bounds_np,
    find_band,
    unify_dict,
)
from symbols import Symbols
from wsocket import Wsocket
from utils import retry_until_not_none
from constants import logging
from traceback import print_exc
from toolkit.kokoo import blink, is_time_past, timer


class Oneside:
    def __init__(self, settings, symbol_settings, ce_or_pe="call"):
        self.symbols = Symbols(**symbol_settings)
        self.quantity = settings["quantity"]
        self.stop_loss = settings["stop_loss"]
        self.target = settings["target"]
        self.expiry_offset = settings.get("expiry_offset", 1)
        # self.expiry = self.symbols.get_expiry(expiry_offset=self.expiry_offset)
        self.help = Helper(settings["quantity"])
        self.ce_or_pe = Calls() if ce_or_pe == "call" else Puts()

        logging.debug("subscribing index from symbols yml automtically")
        self.ws: object = Wsocket()
        self.quotes = False
        while not self.quotes or not any(self.quotes):
            self.quotes = self.ws.ltp()

        logging.debug("decipher ltp from websocket response")

        # build option chain
        bn_ltp = self.ltp_from_ws_response(
            [self.symbols.instrument_token, self.symbols.tradingsymbol]
        )
        tokens = self.symbols.build_chain(bn_ltp, full_chain=True)
        self.quotes = self.ws.ltp(tokens)
        ce_symbol, pe_symbol = self.symbols.get_option_symbols(bn_ltp)
        self.ce_or_pe.tradingsymbol = (
            ce_symbol if isinstance(self.ce_or_pe, Calls) else pe_symbol
        )
        self.ce_or_pe.instrument_token = self.symbols.tokens_from_symbols(
            self.ce_or_pe.tradingsymbol
        )[0]["instrument_token"]
        self.line = self.ltp_from_ws_response(
            [self.ce_or_pe.instrument_token, self.ce_or_pe.tradingsymbol]
        )
        self.short()

    @retry_until_not_none
    def ltp_from_ws_response(self, lst):
        try:
            self.quotes = self.ws.ltp()
            last_price = [
                d["last_price"] for d in self.quotes if d["instrument_token"] == lst[0]
            ][0]
            if last_price is None:
                raise Exception("price is None")
            return last_price
        except Exception as e:
            print(f"ltp error: {e}")
            print_exc()

    def short(self):
        try:
            last_price = self.ltp_from_ws_response(
                [self.ce_or_pe.instrument_token, self.ce_or_pe.tradingsymbol]
            )
            params = {
                "symbol": self.ce_or_pe.tradingsymbol,
                "side": "SELL",
                "order_type": "MARKET",
                "last_price": last_price,
            }
            self.ce_or_pe.short_id = self.help.enter(params)
            self.ce_or_pe.short_params = params
            logging.info(f"short_id: {self.ce_or_pe.short_id}")
            logging.debug(f"short params: {self.ce_or_pe.short_params}")

            params["side"] = "BUY"
            params["order_type"] = "SL"
            params["quantity"] = self.quantity
            params["trigger_price"] = params["last_price"] + self.stop_loss
            params["price"] = params["trigger_price"] + 5
            params["tag"] = "stoploss"

            self.ce_or_pe.buy_id = self.help.enter(params)
            self.ce_or_pe.buy_params = params
            logging.info(f"buy_id: {self.ce_or_pe.buy_id}")
            logging.debug(f"buy params: {self.ce_or_pe.buy_params}")
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

    def set_bounds_to_check(self):
        # update last price for each dictionary
        lst = unify_dict(self.sr, self.quotes, "instrument_token")
        lst_of_bands, lst_of_prices = find_band(lst)
        median = self.ce_or_pe.buy_params["last_price"]
        lst_of_bands.append((median - self.stop_loss, median + self.target))
        lst_of_prices.append(median)
        logging.info("setting bounds", lst_of_bands, lst_of_prices)
        self.ce_or_pe.bounds = lst_of_bands, lst_of_prices

    def is_price(self, above_or_below="above"):
        if above_or_below == "above":
            if (
                self.ce_or_pe.buy_params["last_price"]
                > self.ce_or_pe.buy_params["trigger_price"]
            ):
                logging.info(
                    f"price above buy order {self.ce_or_pe.buy_params['trigger_price']}"
                )
                return True
        else:
            if self.ce_or_pe.short_params["last_price"] < self.line:
                logging.info(
                    f"{self.ce_or_pe.short_params['last_price']} is below base price {self.line}"
                )
                return True

        return False

    def run(self):
        try:
            while not is_time_past(O_SETG["program"]["stop"]):
                self.orders = self.help.api().orders
                self.quotes = self.ws.ltp()
                last_price = self.ltp_from_ws_response(
                    [self.ce_or_pe.instrument_token, self.ce_or_pe.tradingsymbol]
                )
                if last_price:
                    self.ce_or_pe.buy_params["last_price"] = last_price
                    self.ce_or_pe.short_params["last_price"] = last_price
                if self.ce_or_pe.status == -1:
                    subset = {"order_id": self.ce_or_pe.buy_id, "status": "COMPLETE"}
                    if self.is_order_complete(subset):
                        self.ce_or_pe.status = 0
                    elif self.is_price("above"):
                        self.ce_or_pe.buy_params["order_id"] = self.ce_or_pe.buy_id
                        self.help.cover_and_buy(self.ce_or_pe.buy_params)
                        self.ce_or_pe.status = 0
                    ## status is a fresh buy
                elif self.ce_or_pe.status == 0 and self.is_price("below"):
                    logging.info({self.ce_or_pe.tradingsymbol: self.ce_or_pe.status})
                    # short new position
                    self.short()
                    self.ce_or_pe.status = -1
                    logging.info({self.ce_or_pe.tradingsymbol: self.ce_or_pe.status})
                # print(self.help.api().positions)
                blink()
                print(vars(self.ce_or_pe))
            else:
                lst_of_orders = self.help.api().orders
                for order in lst_of_orders:
                    try:
                        if order["status"] in ["OPEN", "TRIGGER PENDING", None]:
                            params = dict(
                                order_id=order["order_id"], variety=order["variety"]
                            )
                            self.help.api().order_cancel(**params)
                    except Exception as e:
                        logging.error(f"order {order} cancel error: {e}")
                lst_of_pos = self.help.api().positions
                for pos in lst_of_pos:
                    if pos["quantity"] != 0:
                        side = "SELL" if pos["quantity"] > 0 else "BUY"
                        instrument_token = (
                            self.ce_or_pe.instrument_token
                            if self.ce_or_pe.tradingsymbol == pos["symbol"]
                            else self.ce_or_pe.instrument_token
                        )
                        last_price = self.ltp_from_ws_response(
                            [instrument_token, pos["symbol"]]
                        )
                        args = dict(
                            symbol=pos["symbol"],
                            side=side,
                            order_type="MARKET",
                            tag="exit",
                            last_price=last_price,
                        )
                        logging.info(args)
                        resp = self.help.enter(args)
                        logging.info(f"exit: {resp}")
                # cancel orders
        except Exception as e:
            logging.error(f"run error: {e}")
            print_exc()
            timer(5)
            print("TRYING TO RECOVER")
            Helper.api_object = None
            self.help.api()
            self.run()


if __name__ == "__main__":
    print("test")
    from constants import O_SETG, logging
    from symbols import dump
    from utils import dict_from_yml

    try:
        # download necessary masters
        dump()
        strategy_settings = O_SETG["strategy"]
        # Unpack settings into instance attributes
        symbol_settings = dict_from_yml("base", strategy_settings["base"])
        Oneside(strategy_settings, symbol_settings).run()
    except Exception as e:
        print(e)
        print_exc()

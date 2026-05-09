from integrations.api import Helper
from core.models import Calls, Puts
from engine.signals import check_any_out_of_bounds_np
from engine.symbols import Symbols
from integrations.wsocket import Wsocket
from core.utils import retry_until_not_none
from traceback import print_exc
from toolkit.kokoo import blink, is_time_past, timer
from core.config import load_symbols
import pendulum

class Oneside:
    def __init__(self, config, symbol_settings, logging, ce_or_pe="call"):
        self.config = config
        self.logging = logging
        strategy_settings = config.strategy
        self.symbols = Symbols(logging, **symbol_settings)
        self.quantity = strategy_settings["quantity"]
        self.stop_loss = strategy_settings["stop_loss"]
        self.target = strategy_settings["target"]
        self.ttl = strategy_settings.get("ttl")
        self.expiry_offset = strategy_settings.get("expiry_offset", 1)
        self.help = Helper(self.quantity, config, logging)
        self.ce_or_pe = Calls() if ce_or_pe == "call" else Puts()

        self.logging.debug("subscribing index from symbols yml automtically")
        d_symbol = load_symbols()
        self.ws = Wsocket(config, d_symbol, logging, self.help)
        self.quotes = False
        while not self.quotes or not any(self.quotes):
            self.quotes = self.ws.ltp()

        self.logging.debug("decipher ltp from websocket response")
        bn_ltp = self.ltp_from_ws_response(
            [self.symbols.instrument_token, self.symbols.tradingsymbol]
        )
        tokens = self.symbols.build_chain(bn_ltp, full_chain=True)
        self.quotes = self.ws.ltp(tokens)

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
            bn_ltp = self.ltp_from_ws_response(
                [self.symbols.instrument_token, self.symbols.tradingsymbol]
            )
            ce_symbol, pe_symbol = self.symbols.get_option_symbols(bn_ltp)
            self.ce_or_pe.tradingsymbol = (
                ce_symbol if isinstance(self.ce_or_pe, Calls) else pe_symbol
            )
            self.ce_or_pe.instrument_token = self.symbols.tokens_from_symbols(
                self.ce_or_pe.tradingsymbol
            )[0]["instrument_token"]
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
            self.logging.info(f"short_id: {self.ce_or_pe.short_id}")
            self.logging.debug(f"short params: {self.ce_or_pe.short_params}")

            params["side"] = "BUY"
            params["order_type"] = "SL"
            params["quantity"] = self.quantity * 2
            params["trigger_price"] = params["last_price"] + self.stop_loss
            params["price"] = params["trigger_price"] + 5
            params["tag"] = "stoploss"

            self.ce_or_pe.buy_id = self.help.enter(params)
            self.ce_or_pe.buy_params = params
            self.logging.info(f"buy_id: {self.ce_or_pe.buy_id}")
            self.logging.debug(f"buy params: {self.ce_or_pe.buy_params}")
        except Exception as e:
            self.logging.error(f"short error: {e}")
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
                    self.logging.info(f"{subset} found")
                    break
        except Exception as e:
            self.logging.info(f" is_order_complete error: {e}")
        finally:
            return flag

    def set_bounds_to_check(self):
        median = self.ce_or_pe.buy_params["last_price"]
        lst_of_bands = (median - self.stop_loss, median + self.target)
        self.ce_or_pe.bounds = [lst_of_bands], [median]
        self.logging.info(f"setting bounds {str(lst_of_bands)} {median=}")

    def is_price_above(self):
        if self.ce_or_pe.buy_params["last_price"] > self.ce_or_pe.buy_params["price"]:
            self.logging.info(f"price above buy order {self.ce_or_pe.buy_params['price']}")
            return True
        return False

    def run(self):
        try:
            while not is_time_past(O_SETG["program"]["stop"]):
                self.orders = self.help.api().orders
                self.quotes = self.ws.ltp()
                if getattr(self.ce_or_pe, "buy_params", None):
                    last_price = self.ltp_from_ws_response(
                        [self.ce_or_pe.instrument_token, self.ce_or_pe.tradingsymbol]
                    )
                    self.ce_or_pe.short_params["last_price"] = self.ce_or_pe.buy_params[
                        "last_price"
                    ] = last_price

                if self.ce_or_pe.status == -1:
                    subset = {"order_id": self.ce_or_pe.buy_id, "status": "COMPLETE"}
                    if self.is_order_complete(subset):
                        self.ce_or_pe.status = 1
                    elif self.is_price_above():
                        self.ce_or_pe.buy_params["order_id"] = self.ce_or_pe.buy_id
                        self.help.cover_and_buy(self.ce_or_pe.buy_params)
                        self.ce_or_pe.status = 1
                    ## status is a fresh buy
                    if self.ce_or_pe.status == 1:
                        self.set_bounds_to_check()
                        self.logging.info(
                            {self.ce_or_pe.tradingsymbol: self.ce_or_pe.status}
                        )
                    print(vars(self.ce_or_pe))
                elif self.ce_or_pe.status == 1:
                    """
                    lst = unify_dict(self.sr, self.quotes, "instrument_token")
                    lst_of_prices = [d["last_price"] for d in lst]
                    """
                    last_price_of_option = self.ltp_from_ws_response(
                        [self.ce_or_pe.instrument_token, self.ce_or_pe.tradingsymbol]
                    )
                    first, _ = self.ce_or_pe.bounds
                    self.ce_or_pe.bounds = first, [last_price_of_option]
                    print(self.ce_or_pe.bounds)
                    if check_any_out_of_bounds_np(self.ce_or_pe.bounds):
                        self.logging.info("out of bounds, exiting buy trade")
                        # sell existing position
                        kwargs = self.ce_or_pe.buy_params.copy()
                        kwargs["quantity"] = self.quantity
                        kwargs["side"] = "SELL"
                        kwargs["order_type"] = "MARKET"
                        kwargs["price"] = 0.0
                        kwargs["tag"] = "exit"
                        kwargs.pop("order_id", None)
                        self.help.enter(kwargs)
                        self.ce_or_pe.status = 0
                elif self.ce_or_pe.status == 0:
                    # short new position
                    self.short()
                    self.ce_or_pe.status = -1
                    self.logging.info({self.ce_or_pe.tradingsymbol: self.ce_or_pe.status})
                # print(self.help.api().positions)
                blink()
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
                        self.logging.error(f"order {order} cancel error: {e}")
                lst_of_pos = self.help.api().positions
                for pos in lst_of_pos:
                    if pos["quantity"] != 0:
                        side = "SELL" if pos["quantity"] > 0 else "BUY"
                        instrument_token = (
                            self.ce_or_pe.instrument_token
                            if self.ce_or_pe.tradingsymbol == pos["symbol"]
                            else self.symbols.tokens_from_symbols(pos["symbol"])[0][
                                "instrument_token"
                            ]
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
                        self.logging.info(args)
                        resp = self.help.enter(args)
                        self.logging.info(f"exit: {resp}")
                # cancel orders
            #
        except Exception as e:
            self.logging.error(f"run error: {e}")
            print_exc()
            timer(5)
            print("TRYING TO RECOVER")
            Helper.api_object = None
            self.help.api()
            self.run()


if __name__ == "__main__":
    print("test")
    from core.config import get_config, set_logger
    from engine.symbols import dump
    from core.utils import dict_from_yml

    try:
        config = get_config()
        logging = set_logger(config.log)
        # download necessary masters
        dump()
        strategy_settings = config.strategy
        # Unpack settings into instance attributes
        symbol_settings = dict_from_yml("base", strategy_settings["base"])
        Oneside(config, symbol_settings, logging).run()
    except Exception as e:
        print(e)
        print_exc()
e=side,
                            order_type="MARKET",
                            tag="exit",
                            last_price=last_price,
                        )
                        self.logging.info(args)
                        resp = self.help.enter(args)
                        self.logging.info(f"exit: {resp}")
                # cancel orders
            #
        except Exception as e:
            self.logging.error(f"run error: {e}")
            print_exc()
            timer(5)
            print("TRYING TO RECOVER")
            Helper.api_object = None
            self.help.api()
            self.run()


if __name__ == "__main__":
    print("test")
    from core.config import get_config, set_logger
    from engine.symbols import dump
    from core.utils import dict_from_yml

    try:
        config = get_config()
        logging = set_logger(config.log)
        # download necessary masters
        dump()
        strategy_settings = config.strategy
        # Unpack settings into instance attributes
        symbol_settings = dict_from_yml("base", strategy_settings["base"])
        Oneside(config, symbol_settings, logging).run()
    except Exception as e:
        print(e)
        print_exc()

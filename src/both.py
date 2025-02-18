from api import Helper
from models import Calls, Puts
from signals import (
    check_any_out_of_bounds_np,
    find_band,
    pfx_and_sfx,
    read_supp_and_res,
    unify_dict,
)
from symbols import Symbols
from wsocket import Wsocket
from utils import retry_until_not_none
from constants import logging, O_SETG
from traceback import print_exc
from toolkit.kokoo import blink, is_time_past, timer


class Both:
    def __init__(self, settings, symbol_settings):
        self.symbols = Symbols(**symbol_settings)
        self.quantity = settings["quantity"]
        self.stop_loss = settings["stop_loss"]
        self.target = settings["target"]
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
        bn_ltp = self.ltp_from_ws_response(
            [self.symbols.instrument_token, self.symbols.tradingsymbol]
        )
        tokens = self.symbols.build_chain(bn_ltp, full_chain=True)
        self.quotes = self.ws.ltp(tokens)

        # subscribe to support and resistance
        self.quotes = self.ws.ltp(self.sr)

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

    def short(self, option):
        try:
            bn_ltp = self.ltp_from_ws_response(
                [self.symbols.instrument_token, self.symbols.tradingsymbol]
            )
            ce_symbol, pe_symbol = self.symbols.get_option_symbols(bn_ltp)
            option.tradingsymbol = ce_symbol if isinstance(option, Calls) else pe_symbol
            option.instrument_token = self.symbols.tokens_from_symbols(
                option.tradingsymbol
            )[0]["instrument_token"]
            last_price = self.ltp_from_ws_response(
                [option.instrument_token, option.tradingsymbol]
            )
            params = {
                "symbol": option.tradingsymbol,
                "side": "SELL",
                "order_type": "MARKET",
                "last_price": last_price,
            }
            option.short_id = self.help.enter(params)
            option.short_params = params
            logging.info(f"short_id: {option.short_id}")
            logging.debug(f"short params: {option.short_params}")
            
            params["side"] = "BUY"
            params["order_type"] = "SL"
            params["quantity"] = self.quantity * 2
            params["trigger_price"] = params["last_price"] + self.stop_loss
            params["price"] = params["trigger_price"] + 2
            params["tag"] = "stoploss"

            option.buy_id = self.help.enter(params)
            logging.info(f"buy_id: {option.buy_id}")
            logging.debug(f"buy params: {option.buy_params}")
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
                    logging.info(f"{subset} found")
                    break
        except Exception as e:
            logging.info(f" is_order_complete error: {e}")
        finally:
            return flag

    def set_bounds_to_check(self, opt):
        # update last price for each dictionary
        lst = unify_dict(self.sr, self.quotes, "instrument_token")
        lst_of_bands, lst_of_prices = find_band(lst)
        #TODO change param last price to price
        median = opt.buy_params["price"]
        logging.info(f"price for target and stop calculation is {median}")
        lst_of_bands.append((median - self.stop_loss, median + self.target))
        lst_of_prices.append(median)
        opt.bounds = lst_of_bands, lst_of_prices
        logging.info("setting bounds", str(lst_of_bands), str(lst_of_prices))

    def is_price_above(self, option):
        if option.buy_params["last_price"] > option.buy_params["price"]:
            logging.info(f"price above buy order {option.buy_params['price']}")
            return True
        return False

    def run(self):
        try:
            while not is_time_past(O_SETG["program"]["stop"]):
                self.orders = self.help.api().orders
                self.quotes = self.ws.ltp()
                lst = [self.ce, self.pe]
                for opt in lst:
                    """
                    if getattr(opt, "buy_params", None):
                        last_price = self.ltp_from_ws_response(
                            [opt.instrument_token, opt.tradingsymbol]
                        )
                        opt.buy_params["last_price"] = last_price
                        opt.short_params["last_price"] = last_price
                    """
                    if opt.status == -1:
                        subset = {"order_id": opt.buy_id, "status": "COMPLETE"}
                        # is stop loss hit
                        if self.is_order_complete(subset):
                            opt.status = 1
                        """
                        elif self.is_price_above(opt):
                            opt.buy_params["order_id"] = opt.buy_id
                            self.help.cover_and_buy(opt.buy_params)
                            opt.status = 1
                        """
                        ## status is a fresh buy
                        if opt.status == 1:
                            self.set_bounds_to_check(opt)
                            logging.info(f"{opt.tradingsymbol} hit stop loss")
                        print(vars(opt))
                    elif opt.status == 1:
                        lst = unify_dict(self.sr, self.quotes, "instrument_token")
                        lst_of_prices = [d["last_price"] for d in lst]
                        last_price_of_option = self.ltp_from_ws_response(
                            [opt.instrument_token, opt.tradingsymbol]
                        )
                        lst_of_prices.append(last_price_of_option)
                        opt.bounds = opt.bounds[0], lst_of_prices
                        print(opt.bounds)
                        if check_any_out_of_bounds_np(opt.bounds):
                            logging.info("out of bounds, exiting buy trade")
                            """
                            kwargs = opt.buy_params.copy()
                            kwargs["quantity"] = self.quantity
                            kwargs["side"] = "SELL"
                            kwargs["order_type"] = "MARKET"
                            kwargs["price"] = 0.0
                            kwargs["tag"] = "exit"
                            kwargs.pop("order_id", None)
                            """
                            # sell existing position
                            params = opt.short_params
                            params["last_price"] = last_price_of_option
                            self.help.enter(kwargs)
                            opt.status = 0
                            
                    if opt.status == 0:
                        # short new position
                        self.short(opt)
                        opt.status = -1
                        logging.info(f"new short for {opt.tradingsymbol}")
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
                        logging.error(f"order {order} cancel error: {e}")
                lst_of_pos = self.help.api().positions
                for pos in lst_of_pos:
                    if pos["quantity"] != 0:
                        side = "SELL" if pos["quantity"] > 0 else "BUY"
                        instrument_token = (
                            self.ce.instrument_token
                            if self.ce.tradingsymbol == pos["symbol"]
                            else self.pe.instrument_token
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
            #
        except Exception as e:
            logging.error(f"run error: {e}")
            print_exc()
            timer(5)
            print("TRYING TO RECOVER")
            Helper.api_object = None
            self.help.api()
            self.run()

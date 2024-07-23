from constants import O_SETG, logging, O_CNFG, S_DATA, O_FUTL
from typing import List
from traceback import print_exc
import pandas as pd
import pendulum as plum
from paper import Paper



def build_order(exchange, tradingsymbol, transaction_type, quantity):
    order = {}
    order["exchange"] = exchange
    order["tradingsymbol"] = tradingsymbol
    order["transaction_type"] = transaction_type
    order["quantity"] = quantity
    order["order_type"] = "MARKET"
    return order


def get_bypass():
    from stock_brokers.bypass.bypass import Bypass

    try:
        dct = O_CNFG["bypass"]
        tokpath = S_DATA + dct["userid"] + ".txt"
        enctoken = None
        if not O_FUTL.is_file_not_2day(tokpath):
            print(f"{tokpath} modified today ... reading {enctoken}")
            with open(tokpath, "r") as tf:
                enctoken = tf.read()
                if len(enctoken) < 5:
                    enctoken = None
        print(f"enctoken to broker {enctoken}")
        if O_SETG["live"]:
            bypass = Bypass(
                dct["userid"], dct["password"], dct["totp"], tokpath, enctoken
            )
        else:
            bypass = Paper(
                dct["userid"], dct["password"], dct["totp"], tokpath, enctoken
            )
        if bypass.authenticate():
            if not enctoken:
                enctoken = bypass.kite.enctoken
                with open(tokpath, "w") as tw:
                    tw.write(enctoken)
        else:
            raise Exception("unable to authenticate")
    except Exception as e:
        print(f"unable to create bypass object {e}")
        print_exc()
    else:
        return bypass


def get_zerodha():
    try:
        from stock_brokers.zerodha.zerodha import Zerodha

        dct = O_CNFG["zerodha"]
        zera = Zerodha(
            user_id=dct["userid"],
            password=dct["password"],
            totp=dct["totp"],
            api_key=dct["api_key"],
            secret=dct["secret"],
            tokpath=S_DATA + dct["userid"] + ".txt",
        )
        if not zera.authenticate():
            raise Exception("unable to authenticate")

    except Exception as e:
        print(f"exception while creating zerodha object {e}")
    else:
        return zera


def remove_token(tokpath):
    __import__("os").remove(tokpath)


def login():
    if O_CNFG["broker"] == "bypass":
        return get_bypass()
    else:
        return get_zerodha()

class Order:
    quantity = 0

    @classmethod
    def set_quantity(cls, quantity):
        cls.quantity = quantity

    def __init__(self):
        self.quantity = Order.quantity  # Access class-level quantity

    def to_dict(self):
        return {
            "quantity": self.quantity,
            "order_type": "MARKET",
            "product": "MIS",
            "validity": "DAY",
            "tag": "enter"
        }


class Helper:
    api_object = None
    buy = []

    @classmethod
    def api(cls):
        if cls.api_object is None:
            cls.api_object = login()
        return cls.api_object

    def __init__(self, initial_quantity):
        Order.set_quantity(initial_quantity)

    def modify_to_close(self, kwargs):
        """
        modifies order from order book 

        args: 
            order_id: id of order to be modified
            ltp: used for paper trades
        returns: 
            modify response
        """
        try:
            params = dict(
                order_id=kwargs["order_id"],
                order_type="MARKET",
                price=0.0,
                variety="regular",
                ltp=kwargs.get("ltp", 0)
            )
            return self.api().order_modify(**params)
        except Exception as e:
            logging.error(f"exit: {e}")
            print_exc()

    def order_place(self, kwargs):
        """
        place order and can overload default order params

        args: 
            symbol, side, quantity, price, trigger_price, ltp
        returns:
            order place response
        """
        try:
            params = Order().to_dict()
            params.update(kwargs)
            return self.api().order_place(**params)
        except Exception as e:
            logging.error(f"enter: {e}")
            print_exc()

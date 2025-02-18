from traceback import print_exc

from constants import O_CNFG, O_FUTL, O_SETG, S_DATA, logging
from models import Order
from paper import Paper


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
        remove_token(tokpath)
        get_bypass()
        print_exc()
    else:
        return bypass


def get_zerodha():
    try:
        from stock_brokers.zerodha.zerodha import Zerodha

        dct = O_CNFG["zerodha"]
        tokpath = S_DATA + dct["userid"] + ".txt"
        zera = Zerodha(
            user_id=dct["userid"],
            password=dct["password"],
            totp=dct["totp"],
            api_key=dct["api_key"],
            secret=dct["secret"],
            tokpath=tokpath,
        )
        if not zera.authenticate():
            raise Exception("unable to authenticate")

    except Exception as e:
        print(f"exception while creating zerodha object {e}")
        remove_token(tokpath)
        get_zerodha()
    else:
        return zera


def remove_token(tokpath):
    __import__("os").remove(tokpath)


def login():
    if O_CNFG["broker"] == "bypass":
        return get_bypass()
    else:
        return get_zerodha()


class Helper:
    api_object = None

    @classmethod
    def api(cls):
        if cls.api_object is None:
            cls.api_object = login()
        return cls.api_object

    def __init__(self, initial_quantity):
        Order.set_quantity(initial_quantity)

    def cover_and_buy(self, kwargs):
        """
        modifies order from order book

        args:
            order_id: id of order to be modified
            ltp: used for paper trades
        returns:
            modify response
        """
        try:
            logging.warning("MODIFYING stop order that is not complete")
            kwargs["order_type"] = "MARKET"
            kwargs["price"] = 0.0
            return self.api().order_modify(kwargs)
        except Exception as e:
            logging.error(f"exit: {e}")
            print_exc()

    def enter(self, kwargs):
        """
        place order and can overload default order params

        args:
            symbol, side, price, trigger_price, ltp
        returns:
            order place response
        """
        try:
            params = Order().to_dict()
            params.update(kwargs)
            print(params)
            return self.api().order_place(**params)
        except Exception as e:
            logging.error(f"enter: {e}")
            print_exc()

    def find_fillprice_from_order_id(self, order_id):
        try:
            lst_of_trades = self.api().trades
            lst_of_average_prices = [
                trade["average_price"]
                for trade in lst_of_trades
                if trade["order_id"] == order_id
            ]
            return sum(lst_of_average_prices) / len(lst_of_average_prices)
        except Exception as e:
            print_exc()
            logging.error(f"{e} while find fill price from trade id")


if __name__ == "__main__":
    import pandas as pd

    quantity = 15
    help = Helper(15)
    """
    params = {
        "symbol": "NIFTY100CE",
        "side": "SELL",
        "order_type": "MARKET",
        "last_price": 20,
    }
    short_id = help.enter(params)
    short_params = params
    logging.info(f"short_id: {short_id}")
    logging.debug(f"short params: {params}")

    params["side"] = "BUY"
    params["order_type"] = "SL"
    params["quantity"] = quantity * 2
    params["trigger_price"] = params["last_price"] + 60
    params["tag"] = "stoploss"

    buy_id = help.enter(params)
    buy_params = params
    logging.info(f"buy_id: {buy_id}")
    logging.debug(f"buy params: {params}")

    #exit
    buy_params["order_id"] = buy_id
    help.exit(buy_params)
    """
    ord = help.api().orders
    print(ord)
    if any(ord):
        df = pd.DataFrame(ord)
        df = df[
            [
                "symbol",
                "quantity",
                "side",
                "order_timestamp",
                "order_id",
                "average_price",
                "status",
            ]
        ]
        print(df)
        df = df.to_csv(S_DATA + "orders.csv", index=False)
        pos = help.api().positions
        df = pd.DataFrame(pos)
        df = df[["symbol", "quantity", "unrealised", "m2m"]]
        print(df)

from traceback import print_exc
from core.models import Order
from integrations.paper import Paper

def get_bypass(config, logging):
    from stock_brokers.bypass.bypass import Bypass
    try:
        tokpath = "../data/" + config.userid + ".txt"
        enctoken = None
        # Using a dummy check since O_FUTL was inside constants
        # In a real refactor, we should move O_FUTL to utils or core_config
        from toolkit.fileutils import Fileutils
        O_FUTL = Fileutils()
        
        if not O_FUTL.is_file_not_2day(tokpath):
            print(f"{tokpath} modified today ... reading {enctoken}")
            with open(tokpath, "r") as tf:
                enctoken = tf.read()
                if len(enctoken) < 5:
                    enctoken = None
        print(f"enctoken to broker {enctoken}")
        if config.live:
            bypass = Bypass(
                config.userid, config.password, config.totp, tokpath, enctoken
            )
        else:
            from core.config import S_DATA
            slippage = config.strategy.get("slippage", 0.0)
            bypass = Paper(
                config.userid, 
                config.password, 
                config.totp, 
                tokpath, 
                enctoken, 
                logging=logging,
                data_dir=S_DATA,
                slippage_pct=slippage
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
        get_bypass(config, logging)
        print_exc()
    else:
        return bypass

def get_zerodha(config, logging):
    try:
        from stock_brokers.zerodha.zerodha import Zerodha
        tokpath = "../data/" + config.userid + ".txt"
        zera = Zerodha(
            user_id=config.userid,
            password=config.password,
            totp=config.totp,
            api_key=config.api_key,
            secret=config.secret,
            tokpath=tokpath,
        )
        if not zera.authenticate():
            raise Exception("unable to authenticate")
    except Exception as e:
        print(f"exception while creating zerodha object {e}")
        remove_token(tokpath)
        get_zerodha(config, logging)
    else:
        return zera

def remove_token(tokpath):
    import os
    if os.path.exists(tokpath):
        os.remove(tokpath)

def login(config, logging):
    if config.broker == "bypass":
        return get_bypass(config, logging)
    else:
        return get_zerodha(config, logging)

class Helper:
    api_object = None

    @classmethod
    def api(cls, config=None, logging=None):
        if cls.api_object is None:
            if config is None or logging is None:
                raise ValueError("Config and logging must be provided for initial login")
            cls.api_object = login(config, logging)
        return cls.api_object

    def __init__(self, initial_quantity, config, logging):
        self.config = config
        self.logging = logging
        Order.set_quantity(initial_quantity)
        Helper.api(config, logging)

    def cover_and_buy(self, kwargs):
        try:
            self.logging.warning("MODIFYING stop order that is not complete")
            kwargs["order_type"] = "MARKET"
            kwargs["price"] = 0.0
            return self.api().order_modify(kwargs)
        except Exception as e:
            self.logging.error(f"exit: {e}")
            print_exc()

    def enter(self, kwargs):
        try:
            params = Order().to_dict(self.config.strategy)
            params.update(kwargs)
            print(params)
            return self.api().order_place(**params)
        except Exception as e:
            self.logging.error(f"enter: {e}")
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
            self.logging.error(f"{e} while find fill price from trade id")


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
                "tag",
            ]
        ]
        print(df)
        df = df.to_csv(S_DATA + "orders.csv", index=False)
        pos = help.api().positions
        df = pd.DataFrame(pos)
        df = df[["symbol", "quantity", "unrealised", "m2m"]]
        print(df)

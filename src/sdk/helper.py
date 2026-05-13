from traceback import print_exc
from constants import CNFG, logging
from core.models import Order

def get_delta_india():
    try:
        from broker_ai.broker import BrokerAI
        broker = BrokerAI(
            userid=CNFG.get("userid"),
            password=CNFG.get("password"),
            totp=CNFG.get("totp"),
            api_key=CNFG.get("api_key"),
            secret=CNFG.get("secret"),
            logging=logging
        )
        if broker.authenticate():
            return broker
        else:
            raise Exception("unable to authenticate with delta-india via broker-ai")
    except Exception as e:
        logging.error(f"unable to create delta-india object {e}")
        print_exc()
        return None

def login():
    broker = CNFG.get("broker", "bypass")
    if broker == "delta-india" or broker == "bypass":
        return get_delta_india()
    else:
        return get_delta_india()

class RestApi:
    api_object = None

    @classmethod
    def api(cls):
        if cls.api_object is None:
            cls.api_object = login()
        return cls.api_object

    def __init__(self, initial_quantity):
        Order.set_quantity(initial_quantity)
        RestApi.api()

    def cover_and_buy(self, kwargs):
        try:
            logging.warning("MODIFYING stop order that is not complete")
            kwargs["order_type"] = "MARKET"
            kwargs["price"] = 0.0
            return self.api().order_modify(kwargs)
        except Exception as e:
            logging.error(f"exit: {e}")
            print_exc()

    def enter(self, kwargs):
        try:
            params = Order().to_dict(CNFG.get("strategy", {}))
            params.update(kwargs)
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
            if lst_of_average_prices:
                return sum(lst_of_average_prices) / len(lst_of_average_prices)
            return 0.0
        except Exception as e:
            print_exc()
            logging.error(f"{e} while find fill price from trade id")

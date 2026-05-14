from traceback import print_exc
from constants import CNFG, get_logger
from sdk.models import Order
from broker_ai.delta.delta import Delta

log = get_logger(__name__)


def get_broker() -> Delta:
    try:
        broker = Delta(
            api_key=CNFG.get("api_key"),
            api_secret=CNFG.get("secret"),
        )
        if broker.authenticate():
            return broker
        raise Exception("authentication failed")
    except Exception as e:
        log.error(f"unable to create broker object {e}")
        print_exc()
        raise


class RestApi:
    api_object: Delta | None = None

    @classmethod
    def api(cls) -> Delta:
        if cls.api_object is None:
            cls.api_object = get_broker()
        return cls.api_object

    def __init__(self, initial_quantity: int) -> None:
        Order.set_quantity(initial_quantity)
        RestApi.api()

    def enter(self, kwargs: dict) -> str:
        try:
            params = Order().to_dict(CNFG.get("strategy", {}))
            params.update(kwargs)
            return self.api().order_place(**params)
        except Exception as e:
            log.error(f"enter: {e}")
            print_exc()
            return ""

    def find_fillprice_from_order_id(self, order_id: str) -> float:
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
            log.error(f"{e} while find fill price from trade id")
            return 0.0

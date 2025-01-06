from os import read
from constants import O_SETG
from utils import dict_from_yml


def read_exchange_from_symbol_yml():
    try:
        strategy_settings = O_SETG["strategy"]
        # Unpack settings into instance attributes
        symbol_settings = dict_from_yml("base", strategy_settings["base"])
        return symbol_settings["exchange"]
    except Exception as e:
        print(f"{e} while read_exchange_from_symbol_yml")


class Options:
    def __init__(self):
        self.status = 0
        self.buy_id = 0
        self.buy_params = {}
        self.short_id = 0
        self.short_params = {}
        self.tradingsymbol = ""
        self.instrument_token = 0
        self.bounds = []


class Calls(Options):
    def __init__(self):
        super().__init__()


class Puts(Options):
    def __init__(self):
        super().__init__()


class Order:
    quantity = 0

    @classmethod
    def set_quantity(cls, quantity):
        cls.quantity = quantity

    def __init__(self):
        self.quantity = Order.quantity  # Access class-level quantity

    def to_dict(self):
        return {
            "exchange": read_exchange_from_symbol_yml(),
            "quantity": self.quantity,
            "order_type": "MARKET",
            "product": "MIS",
            "validity": "DAY",
            "tag": "enter",
        }


if __name__ == "__main__":
    resp = read_exchange_from_symbol_yml()
    print(resp)

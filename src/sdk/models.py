from enum import Enum, auto
from typing import Any
from sdk.utils import dict_from_yml


class LegState(Enum):
    FLAT = auto()
    SHORT = auto()
    LONG = auto()
    SHIFTED = auto()


def read_exchange_from_symbol_yml(strategy_settings):
    try:
        # Unpack settings into instance attributes
        symbol_settings = dict_from_yml("base", strategy_settings["base"])
        return symbol_settings["exchange"]
    except Exception as e:
        print(f"{e} while read_exchange_from_symbol_yml")


class Options:
    def __init__(self) -> None:
        self.status: LegState = LegState.FLAT
        self.buy_id: str | int = 0
        self.buy_params: dict[str, Any] = {}
        self.short_id: str | int = 0
        self.short_params: dict[str, Any] = {}
        self.tradingsymbol: str = ""
        self.instrument_token: int = 0
        self.bounds: list[Any] = []
        self.entry_time: Any = None


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

    def to_dict(self, strategy_settings):
        return {
            "exchange": read_exchange_from_symbol_yml(strategy_settings),
            "quantity": self.quantity,
            "order_type": "MARKET",
            "product_type": "NRML",
            "tag": "enter",
        }


if __name__ == "__main__":
    resp = read_exchange_from_symbol_yml({"base": "SENSEX"})
    print(resp)

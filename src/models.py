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
            "exchange": "BFO",
            "quantity": self.quantity,
            "order_type": "MARKET",
            "product": "MIS",
            "validity": "DAY",
            "tag": "enter",
        }


if __name__ == "__main__":
    from pprint import pprint

    c = Calls()
    print("call status", c.status)

    Order.set_quantity(500)
    o = Order().to_dict()
    print("before update")
    pprint(o)
    new_dict = {
        "order_type": "LIMIT",
        "some_key": "some_value",
    }
    print("after updating new dict")
    pprint(new_dict)
    o.update(new_dict)
    pprint(o)

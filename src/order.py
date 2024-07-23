class Order:
    quantity = 0

    @classmethod
    def set_quantity(cls, quantity):
        cls.quantity = quantity

    def __init__(self):
        self.order_type = "MARKET"
        self.quantity = Order.quantity  # Access class-level quantity
        self.product = "MIS"
        self.validity = "DAY"

    def to_dict(self):
        return {
            "order_type": self.order_type,
            "quantity": self.quantity,
            "product": self.product,
            "validity": self.validity,
        }

if __name__ == "__main__":
    Order.set_quantity(500)
    o = Order().to_dict()
    new_dict = {
        "order_type": "LIMIT",
        "some_key": "some_value",
    }
    o.update(new_dict)
    print(o)

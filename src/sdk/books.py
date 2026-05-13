from typing import Dict, Any, List
from sdk.helper import RestApi
from constants import logging

class Books:
    def __init__(self):
        self.api = RestApi.api()

    @property
    def positions(self) -> List[Dict[str, Any]]:
        try:
            return self.api.positions
        except Exception as e:
            logging.error(f"Books.positions error: {e}")
            return []

    @property
    def orders(self) -> List[Dict[str, Any]]:
        try:
            return self.api.orders
        except Exception as e:
            logging.error(f"Books.orders error: {e}")
            return []

    def is_order_complete(self, order_id: str) -> bool:
        for o in self.orders:
            if o.get("order_id") == order_id and o.get("status") == "COMPLETE":
                return True
        return False

    def get_position_qty(self, symbol: str) -> int:
        for p in self.positions:
            if p.get("symbol") == symbol:
                return p.get("quantity", 0)
        return 0

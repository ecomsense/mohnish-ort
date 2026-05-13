from broker_ai.delta.symbols import Symbol
from broker_ai.delta.wsocket import Wsocket
from sdk.helper import RestApi
from sdk.order_manager import OrderManager
from strategies.coinshort import Coinshort
from constants import get_logger

log = get_logger(__name__)

class Builder:
    def __init__(self) -> None:
        self.strategies: list[Coinshort] = []

    def build(self, config: dict, symbols: Symbol, api: RestApi,
              ws: Wsocket, underlying_token: int, underlying_symbol: str) -> list[Coinshort]:
        try:
            om = OrderManager(ws=ws, symbols=symbols, api=api, config=config)
            self.strategies.append(Coinshort(
                config=config,
                symbols=symbols,
                api=api,
                om=om,
                underlying_token=underlying_token,
                underlying_symbol=underlying_symbol,
            ))
            return self.strategies
        except Exception as e:
            log.error(f"Builder.build error: {e}")
            return []

from broker_ai.delta.symbols import Symbol
from sdk.helper import RestApi
from strategies.coinshort import Coinshort
from constants import CNFG, S_DATA, get_logger

log = get_logger(__name__)

class Builder:
    def __init__(self) -> None:
        self.strategies: list[Coinshort] = []

    def build(self) -> list[Coinshort]:
        try:
            strategy_name = CNFG.get("strategy_name", "Coinshort")
            if strategy_name == "Coinshort":
                config = CNFG.get("strategy", {})
                base = CNFG.get("base_instrument", {})
                symbols = Symbol(
                    exchange=base.get("exchange", "DELTA"),
                    symbol=base.get("base", "BTC"),
                    data_path=S_DATA,
                )
                api = RestApi(config.get("quantity", 1))
                underlying_token = base.get("instrument_token", 0)
                underlying_symbol = base.get("tradingsymbol", "")
                self.strategies.append(Coinshort(
                    config=config,
                    symbols=symbols,
                    api=api,
                    underlying_token=underlying_token,
                    underlying_symbol=underlying_symbol,
                ))
            return self.strategies
        except Exception as e:
            log.error(f"Builder.build error: {e}")
            return []

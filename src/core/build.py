from sdk.symbol import OptionSymbol
from sdk.helper import RestApi
from strategies.coinshort import Coinshort
from constants import CNFG, get_logger

log = get_logger(__name__)

class Builder:
    def __init__(self) -> None:
        self.strategies: list[Coinshort] = []

    def build(self) -> list[Coinshort]:
        try:
            strategy_name = CNFG.get("strategy_name", "Coinshort")
            if strategy_name == "Coinshort":
                config = CNFG.get("strategy", {})
                symbol_settings = CNFG.get("base_instrument", {})
                symbols = OptionSymbol(**symbol_settings)
                symbols.get_expiry(config.get("expiry_offset", 0))
                api = RestApi(config.get("quantity", 1))
                self.strategies.append(Coinshort(config=config, symbols=symbols, api=api))
            return self.strategies
        except Exception as e:
            log.error(f"Builder.build error: {e}")
            return []

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
                self.strategies.append(Coinshort())
            return self.strategies
        except Exception as e:
            log.error(f"Builder.build error: {e}")
            return []

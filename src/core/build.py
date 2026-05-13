from strategies.delta import Delta
from constants import CNFG, get_logger

log = get_logger(__name__)

class Builder:
    def __init__(self) -> None:
        self.strategies: list[Delta] = []

    def build(self) -> list[Delta]:
        # In a real super-ai pattern, this might read multiple strategy configs
        # For now, we build the Delta strategy as per mohnish-ort
        try:
            strategy_name = CNFG.get("strategy_name", "Delta")
            if strategy_name == "Delta":
                self.strategies.append(Delta())
            return self.strategies
        except Exception as e:
            log.error(f"Builder.build error: {e}")
            return []

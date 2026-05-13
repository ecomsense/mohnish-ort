from strategies.delta import Delta
from constants import CNFG, logging

class Builder:
    def __init__(self):
        self.strategies = []

    def build(self):
        # In a real super-ai pattern, this might read multiple strategy configs
        # For now, we build the Delta strategy as per mohnish-ort
        try:
            strategy_name = CNFG.get("strategy_name", "Delta")
            if strategy_name == "Delta":
                # Extract symbol settings from CNFG
                # (Adapting from main.py's logic)
                symbol_settings = CNFG.get("base_instrument", {}) 
                # Note: In mohnish-ort settings.yml might have different structure
                # I'll need to make sure CNFG has what Delta needs
                self.strategies.append(Delta())
            return self.strategies
        except Exception as e:
            logging.error(f"Builder.build error: {e}")
            return []

from traceback import print_exc
from toolkit.kokoo import blink, is_time_past
from core.config import get_config, load_symbols, set_logger
from engine.symbols import dump
from core.utils import dict_from_yml
from strategies.both import Both
from strategies.oneside import Oneside

def root():
    try:
        config = get_config()
        logging = set_logger(config.log)
        logging.info("HAPPY TRADING")
        
        # download necessary masters
        dump()
        
        entry_time: str = config.program.start
        strategy_settings = config.strategy
        
        # Unpack settings into instance attributes
        symbol_settings = dict_from_yml("base", strategy_settings["base"])
        
        while not is_time_past(entry_time):
            print(f"z #@! zZZ sleeping till {entry_time}")
            blink()
            
        if strategy_settings["type"] == 0:
            Both(config, symbol_settings, logging).run()
        elif strategy_settings["type"] == -1:
            Oneside(config, symbol_settings, logging, "put").run()
        else:
            Oneside(config, symbol_settings, logging).run()
    except Exception as e:
        print(f"root error: {e}")
        print_exc()

if __name__ == "__main__":
    root()

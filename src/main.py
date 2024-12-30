from traceback import print_exc

from toolkit.kokoo import blink, is_time_past, timer

from constants import O_SETG, logging
from symbols import dump
from utils import dict_from_yml
from trading_strategy import TradingStrategy


def root():
    try:
        logging.info("HAPPY TRADING")
        # download necessary masters
        dump()
        entry_time: str = O_SETG["program"]["start"]
        strategy_settings = O_SETG["strategy"]
        # Unpack settings into instance attributes
        symbol_settings = dict_from_yml("base", strategy_settings["base"])
        timer(5)
        while not is_time_past(entry_time):
            print(f"z #@! zZZ sleeping till {entry_time}")
            blink()
        TradingStrategy(strategy_settings, symbol_settings).run()
    except Exception as e:
        print(f"root error: {e}")
        print_exc()


root()

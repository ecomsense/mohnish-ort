from sdk.helper import RestApi
from sdk.wserver import Wserver
from sdk.books import Books
from constants import logging, CNFG
from toolkit.kokoo import is_time_past, blink
import traceback

class Engine:
    def __init__(self, strategies):
        self.strategies = strategies
        self.books = Books()
        self.ws = Wserver()

    def run(self):
        logging.info("Engine started")
        stop_time = CNFG.get("program", {}).get("stop", "15:30")
        
        try:
            while not is_time_past(stop_time):
                for strategy in self.strategies:
                    try:
                        strategy.tick(self.ws, self.books)
                    except Exception as e:
                        logging.error(f"Error in strategy tick: {e}")
                        traceback.print_exc()
                blink()
            
            logging.info("Stop time reached. Cleaning up.")
            for strategy in self.strategies:
                strategy.cleanup(self.books)
                
        except Exception as e:
            logging.error(f"Engine run error: {e}")
            traceback.print_exc()

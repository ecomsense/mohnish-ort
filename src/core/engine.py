from broker_ai.delta.wsocket import Wsocket
from sdk.books import Books
from constants import get_logger, CNFG
from toolkit.kokoo import is_time_past, blink
import traceback

log = get_logger(__name__)

class Engine:
    def __init__(self, strategies: list) -> None:
        self.strategies = strategies
        self.books = Books()
        self.ws = Wsocket(
            api_key=CNFG.get("api_key"),
            api_secret=CNFG.get("secret"),
        )
        self.ws.connect(threaded=True)

    def run(self) -> None:
        log.info("Engine started")
        stop_time = CNFG.get("program", {}).get("stop", "15:30")
        
        try:
            while not is_time_past(stop_time):
                for strategy in self.strategies:
                    try:
                        strategy.tick(self.ws, self.books)
                    except Exception as e:
                        log.error(f"Error in strategy tick: {e}")
                        traceback.print_exc()
                blink()
            
            log.info("Stop time reached. Cleaning up.")
            for strategy in self.strategies:
                strategy.cleanup(self.books)
                
        except Exception as e:
            log.error(f"Engine run error: {e}")
            traceback.print_exc()

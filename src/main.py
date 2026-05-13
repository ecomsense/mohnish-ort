from constants import CNFG, logging
from core.build import Builder
from core.engine import Engine
from toolkit.kokoo import is_time_past, blink
import traceback

def root():
    try:
        logging.info("HAPPY TRADING - DELTA STRATEGY (SUPER-AI PATTERN)")
        
        entry_time: str = CNFG.get("program", {}).get("start", "09:15")
        
        while not is_time_past(entry_time):
            print(f"z #@! zZZ sleeping till {entry_time}")
            blink()
            
        strategies = Builder().build()
        if strategies:
            Engine(strategies).run()
        else:
            logging.error("No strategies built. Exiting.")

    except Exception as e:
        print(f"root error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    root()

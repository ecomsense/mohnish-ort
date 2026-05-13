from constants import CNFG, ensure_paths, init_logging, get_logger
from broker_ai.delta.wsocket import Wsocket
from core.build import Builder
from core.engine import Engine
from toolkit.kokoo import is_time_past, blink
import traceback

def root() -> None:
    try:
        ensure_paths()
        init_logging()
        log = get_logger(__name__)
        log.info("HAPPY TRADING - COINSHORT STRATEGY")

        entry_time: str = CNFG.get("program", {}).get("start", "09:15")
        while not is_time_past(entry_time):
            print(f"z #@! zZZ sleeping till {entry_time}")
            blink()

        ws = Wsocket(
            api_key=CNFG.get("api_key"),
            api_secret=CNFG.get("secret"),
        )
        ws.connect(threaded=True)

        base = CNFG.get("base_instrument", {})
        underlying_token = str(base.get("instrument_token", 0))

        strategies = Builder().build()
        if strategies:
            stop_time = CNFG.get("program", {}).get("stop", "15:30")
            Engine(strategies, ws, [underlying_token], stop_time).run()
        else:
            log.error("No strategies built. Exiting.")

    except Exception as e:
        print(f"root error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    root()

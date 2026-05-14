from constants import CNFG, S_DATA, ensure_paths, init_logging, get_logger
from broker_ai.delta.wsocket import Wsocket
from broker_ai.delta.symbols import Symbol
from sdk.helper import RestApi
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

        config = CNFG.get("strategy", {})
        base = CNFG.get("base_instrument", {})
        symbols = Symbol(
            exchange=base.get("exchange", "DELTA"),
            symbol=base.get("base", "BTC"),
            data_path=S_DATA,
        )
        api = RestApi(config.get("quantity", 1))
        underlying_token = int(base.get("instrument_token", 0))
        underlying_symbol = base.get("tradingsymbol", "")

        strategy = Builder().build(config, symbols, api, ws,
                                   underlying_token, underlying_symbol)
        if strategy:
            Engine(strategy, ws, str(underlying_token)).run()
        else:
            log.error("No strategy built. Exiting.")

    except Exception as e:
        print(f"root error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    root()

from sdk.symbol import OptionSymbol
from sdk.helper import RestApi
from sdk.wserver import Wserver
from sdk.books import Books
from sdk.models import Calls, Puts, Options
from constants import CNFG, get_logger, S_DATA
import pendulum
import os
import json
from traceback import print_exc
from copy import deepcopy

log = get_logger(__name__)


class Delta:
    def __init__(self) -> None:
        log.info("Initializing Delta Strategy (T1)")
        self.strategy_settings: dict = CNFG.get("strategy", {})

        symbol_settings: dict = CNFG.get("base_instrument", {})
        self.symbols: OptionSymbol = OptionSymbol(**symbol_settings)
        self.symbols.get_expiry(self.strategy_settings.get("expiry_offset", 0))

        self.api: RestApi = RestApi(self.strategy_settings.get("quantity", 1))

        self.tier: int = 1
        self.upper_bound: float = 0
        self.lower_bound: float = 0
        self.current_premium: float = 0

        self.ce: Calls = Calls()
        self.pe: Puts = Puts()

        self.load_state()

        if self.upper_bound == 0:
            self.initial_entry()

    def save_state(self) -> None:
        try:
            def opt_to_dict(opt):
                d = deepcopy(vars(opt))
                if d.get("entry_time"):
                    d["entry_time"] = d["entry_time"].isoformat()
                return d

            state = {
                "strategy": {
                    "tier": self.tier,
                    "upper_bound": self.upper_bound,
                    "lower_bound": self.lower_bound,
                    "current_premium": self.current_premium,
                },
                "ce": opt_to_dict(self.ce),
                "pe": opt_to_dict(self.pe)
            }
            os.makedirs(S_DATA, exist_ok=True)
            with open(os.path.join(S_DATA, "delta_state.json"), "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            log.error(f"Error saving state: {e}")

    def load_state(self) -> None:
        try:
            state_path = os.path.join(S_DATA, "delta_state.json")
            if not os.path.exists(state_path):
                return
            with open(state_path, "r") as f:
                state = json.load(f)
            if not state:
                return

            strat = state.get("strategy", {})
            self.tier = strat.get("tier", 1)
            self.upper_bound = strat.get("upper_bound", 0)
            self.lower_bound = strat.get("lower_bound", 0)
            self.current_premium = strat.get("current_premium", 0)

            def dict_to_opt(opt, data):
                for k, v in data.items():
                    if k == "entry_time" and v:
                        v = pendulum.parse(v)
                    setattr(opt, k, v)

            dict_to_opt(self.ce, state.get("ce", {}))
            dict_to_opt(self.pe, state.get("pe", {}))
            log.info(f"Strategy state loaded. Resuming at Tier T{self.tier}.")
        except Exception as e:
            log.error(f"Error loading state: {e}")

    def get_ltp(self, ws: Wserver, instrument_token: int, tradingsymbol: str) -> float:
        quotes = ws.ltp()
        try:
            price = [d["last_price"] for d in quotes if d["instrument_token"] == instrument_token][0]
            return price
        except Exception:
            log.error(f"Could not fetch LTP for {tradingsymbol}")
            return 0.0

    def initial_entry(self) -> None:
        log.info("Executing Initial T1 Neutral Entry")
        # stub - will implement fully

    def tick(self, ws: Wserver, books: Books) -> None:
        try:
            bn_ltp = self.get_ltp(ws, self.symbols.instrument_token, self.symbols.tradingsymbol)
            if bn_ltp == 0:
                return

            for opt in [self.ce, self.pe]:
                if opt.status == -1:
                    if books.is_order_complete(opt.buy_id):
                        log.info(f"{opt.tradingsymbol} SAR hit. Status flipping to LONG.")
                        opt.status = 1
                        opt.entry_time = pendulum.now()
                        opt.buy_params["price"] = opt.buy_params["trigger_price"]
                        self.set_bounds(opt)

                elif opt.status == 1:
                    pass
                    # TTL and OOB checks stub

            if bn_ltp >= self.upper_bound and self.ce.status == 1:
                self.tier += 1
                self.t_upper_protocol(ws)
            elif bn_ltp <= self.lower_bound and self.pe.status == 1:
                self.tier += 1
                self.t_lower_protocol(ws)

            self.save_state()

        except Exception as e:
            log.error(f"Delta tick error: {e}")
            print_exc()

    def set_bounds(self, opt: Options) -> None:
        median = opt.buy_params["price"]
        lst_of_bands = (median - self.strategy_settings["stop_loss"], median + self.strategy_settings["target"])
        opt.bounds = [lst_of_bands], [median]

    def t_upper_protocol(self, ws: Wserver) -> None:
        # stub for T2 upper protocol
        pass

    def t_lower_protocol(self, ws: Wserver) -> None:
        # stub for T2 lower protocol
        pass

    def cleanup(self, books: Books) -> None:
        log.info("Delta Strategy cleanup")
        # stub

from broker_ai.delta.symbols import Symbol
from sdk.helper import RestApi
from sdk.order_manager import OrderManager
from sdk.models import Calls, Puts, Options, LegState
from constants import get_logger
from broker_ai.delta.wsocket import Wsocket
import pendulum
import json
from traceback import print_exc
from copy import deepcopy

log = get_logger(__name__)


class Coinshort:
    def __init__(self, config: dict, symbols: Symbol, api: RestApi,
                 om: OrderManager, underlying_token: int, underlying_symbol: str) -> None:
        log.info("Initializing Coinshort Strategy (T1)")
        self.config = config
        self.symbols = symbols
        self.api = api
        self.om = om
        self.underlying_token = underlying_token
        self.underlying_symbol = underlying_symbol

        self.tier: int = 1
        self.upper_bound: float = 0
        self.lower_bound: float = 0
        self.current_premium: float = 0

        self.ce: Calls = Calls()
        self.pe: Puts = Puts()

        self.load_state()

        if self.upper_bound == 0:
            self.initial_entry()

    @property
    def stop_loss(self) -> float:
        return self.config["stop_loss"]

    @property
    def target(self) -> float:
        return self.config["target"]

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
            from constants import S_DATA
            import os
            os.makedirs(S_DATA, exist_ok=True)
            with open(os.path.join(S_DATA, "coinshort_state.json"), "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            log.error(f"Error saving state: {e}")

    def load_state(self) -> None:
        try:
            from constants import S_DATA
            import os
            state_path = os.path.join(S_DATA, "coinshort_state.json")
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

    def _is_order_complete(self, order_id: str) -> bool:
        return self.om.is_order_complete(order_id)

    def get_ltp(self, ws: Wsocket, instrument_token: int, tradingsymbol: str) -> float:
        price = ws.ltp.get(str(instrument_token))
        if price is not None:
            return price
        log.error(f"Could not fetch LTP for {tradingsymbol}")
        return 0.0

    def initial_entry(self) -> None:
        log.info("Executing Initial T1 Neutral Entry")
        # stub - will implement fully

    def tick(self, ws: Wsocket) -> None:
        try:
            bn_ltp = self.get_ltp(ws, self.underlying_token, self.underlying_symbol)
            if bn_ltp == 0:
                return

            for opt in [self.ce, self.pe]:
                if opt.status == LegState.SHORT:
                    if self._is_order_complete(opt.buy_id):
                        log.info(f"{opt.tradingsymbol} SAR hit. Status flipping to LONG.")
                        opt.status = LegState.LONG
                        opt.entry_time = pendulum.now()
                        opt.buy_params["price"] = opt.buy_params["trigger_price"]
                        self.set_bounds(opt)

                elif opt.status == LegState.LONG:
                    pass
                    # TTL and OOB checks stub

            if bn_ltp >= self.upper_bound and self.ce.status == LegState.LONG:
                self.tier += 1
                self.t_upper_protocol(ws)
            elif bn_ltp <= self.lower_bound and self.pe.status == LegState.LONG:
                self.tier += 1
                self.t_lower_protocol(ws)

            self.save_state()

        except Exception as e:
            log.error(f"Coinshort tick error: {e}")
            print_exc()

    def set_bounds(self, opt: Options) -> None:
        median = opt.buy_params["price"]
        lst_of_bands = (median - self.stop_loss, median + self.target)
        opt.bounds = [lst_of_bands], [median]

    def t_upper_protocol(self, ws: Wsocket) -> None:
        pass

    def t_lower_protocol(self, ws: Wsocket) -> None:
        pass

    def cleanup(self) -> None:
        log.info("Coinshort Strategy cleanup")

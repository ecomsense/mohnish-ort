from sdk.models import Calls, Puts, LegState
from constants import get_logger
import pendulum
import json
from traceback import print_exc
from copy import deepcopy

log = get_logger(__name__)


class Coinshort:
    def __init__(self, config: dict, symbols, api, om,
                 underlying_token: int, underlying_symbol: str) -> None:
        log.info("Initializing Coinshort Strategy (T1)")
        self.config = config
        self.symbols = symbols
        self.api = api
        self.om = om
        self.underlying_token = underlying_token
        self.underlying_symbol = underlying_symbol

        self.tier: int = 1
        self.bounds: list[list[float]] = []
        self.current_premium: float = 0

        self.ce: Calls = Calls()
        self.pe: Puts = Puts()

        self._satellites: list[dict] = []

        self._entry_ce_id: str | None = None
        self._entry_pe_id: str | None = None

        self.load_state()

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
                    "bounds": self.bounds,
                    "current_premium": self.current_premium,
                    "_entry_ce_id": self._entry_ce_id,
                    "_entry_pe_id": self._entry_pe_id,
                },
                "ce": opt_to_dict(self.ce),
                "pe": opt_to_dict(self.pe),
                "satellites": [dict(s, status=s["status"].value) for s in self._satellites],
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
            self.bounds = strat.get("bounds", [])
            self.current_premium = strat.get("current_premium", 0)
            self._entry_ce_id = strat.get("_entry_ce_id")
            self._entry_pe_id = strat.get("_entry_pe_id")

            def dict_to_opt(opt, data):
                for k, v in data.items():
                    if k == "entry_time" and v:
                        v = pendulum.parse(v)
                    setattr(opt, k, v)

            dict_to_opt(self.ce, state.get("ce", {}))
            dict_to_opt(self.pe, state.get("pe", {}))
            self._satellites = state.get("satellites", [])
            for s in self._satellites:
                s["status"] = LegState(s["status"])
            log.info(f"Strategy state loaded. Resuming at Tier T{self.tier}.")
        except Exception as e:
            log.error(f"Error loading state: {e}")

    def _is_order_complete(self, order_id: str) -> bool:
        return self.om.is_order_complete(order_id)

    def _enter_straddle(self, underlying_price: float) -> None:
        log.info(f"Entering T1 neutral straddle at {underlying_price}")
        ce_result = self.om.enter_short(underlying_price, "CE")
        if "error" in ce_result:
            log.warning(f"CE entry failed: {ce_result}")
            return
        self.ce.tradingsymbol = ce_result["symbol"]
        self.ce.instrument_token = int(ce_result["token"])
        self.ce.short_id = ce_result["short_id"]
        self.ce.buy_id = ce_result["sl_id"]
        self.ce.buy_params = {
            "price": ce_result["price"],
            "trigger_price": ce_result["price"] + self.stop_loss,
        }
        self._entry_ce_id = ce_result["short_id"]

        pe_result = self.om.enter_short(underlying_price, "PE")
        if "error" in pe_result:
            log.warning(f"PE entry failed: {pe_result}")
            return
        self.pe.tradingsymbol = pe_result["symbol"]
        self.pe.instrument_token = int(pe_result["token"])
        self.pe.short_id = pe_result["short_id"]
        self.pe.buy_id = pe_result["sl_id"]
        self.pe.buy_params = {
            "price": pe_result["price"],
            "trigger_price": pe_result["price"] + self.stop_loss,
        }
        self._entry_pe_id = pe_result["short_id"]

        log.info(f"Straddle orders placed. CE: {self._entry_ce_id}, PE: {self._entry_pe_id}")

    def _finalize_entry(self, underlying_price: float) -> None:
        ce_price = self.api.find_fillprice_from_order_id(self._entry_ce_id)
        pe_price = self.api.find_fillprice_from_order_id(self._entry_pe_id)
        if ce_price == 0 or pe_price == 0:
            return
        self.current_premium = ce_price + pe_price
        self.bounds.append([underlying_price + self.current_premium,
                            underlying_price - self.current_premium])
        self.ce.status = LegState.SHORT
        self.pe.status = LegState.SHORT
        self._entry_ce_id = None
        self._entry_pe_id = None
        b = self.bounds[-1]
        log.info(f"T1 entry complete. Premium={self.current_premium}, "
                 f"Bounds=[{b[1]}, {b[0]}]")
        self.save_state()

    def tick(self, underlying_price: float) -> None:
        try:
            if underlying_price == 0:
                return

            if not self.bounds:
                if self._entry_ce_id is None:
                    self._enter_straddle(underlying_price)
                elif (self._is_order_complete(self._entry_ce_id)
                      and self._is_order_complete(self._entry_pe_id)):
                    self._finalize_entry(underlying_price)
                return

            for opt in [self.ce, self.pe]:
                self.om.manage_leg(opt, underlying_price)
            for sat in self._satellites:
                if sat["status"] == LegState.SHIFTED and self.om.is_order_complete(sat["buy_id"]):
                    log.info(f"Satellite {sat['tradingsymbol']} SL hit. Exiting.")
                    sat["status"] = LegState.FLAT

            upper, lower = self.bounds[-1]
            if underlying_price >= upper and self.ce.status == LegState.LONG:
                self.tier += 1
                self.t_upper_protocol(underlying_price)
            elif underlying_price <= lower and self.pe.status == LegState.LONG:
                self.tier += 1
                self.t_lower_protocol(underlying_price)

            self.save_state()

        except Exception as e:
            log.error(f"Coinshort tick error: {e}")
            print_exc()

    def _close_satellite(self, tier: int, counter_leg: str = "PE") -> None:
        if tier == 1:
            target = self.pe if counter_leg == "PE" else self.ce
            self.om.api.api().order_cancel(order_id=target.buy_id)
            self.om.exit_position(target.instrument_token, target.tradingsymbol)
            target.status = LegState.FLAT
            log.info(f"Closed T1 {counter_leg} {target.tradingsymbol}")
            return
        for s in self._satellites:
            if s["tier"] == tier and s["status"] != LegState.FLAT:
                self.om.api.api().order_cancel(order_id=s["buy_id"])
                self.om.exit_position(s["instrument_token"], s["tradingsymbol"])
                s["status"] = LegState.FLAT
                log.info(f"Closed T{tier} satellite {s['tradingsymbol']}")

    def t_upper_protocol(self, underlying_price: float) -> None:
        if any(s["tier"] == self.tier for s in self._satellites if s["status"] != LegState.FLAT):
            return
        self._close_satellite(self.tier - 2, "PE")
        log.info(f"T{self.tier} breach at {underlying_price}. Selling T{self.tier} put.")
        result = self.om.enter_short(underlying_price, "PE")
        if "error" in result:
            return
        self._satellites.append({
            "tier": self.tier,
            "option_type": "PE",
            "status": LegState.SHIFTED,
            "tradingsymbol": result["symbol"],
            "instrument_token": int(result["token"]),
            "entry_price": result["price"],
            "buy_id": result["sl_id"],
            "buy_params": {
                "price": result["price"],
                "trigger_price": result["price"] + self.config.get("stop_loss", 500),
            },
        })
        self.current_premium += result["price"]
        self.bounds.append([underlying_price + self.current_premium,
                            underlying_price - self.current_premium])
        b = self.bounds[-1]
        log.info(f"T{self.tier} put sold. New bounds: [{b[1]}, {b[0]}]")

    def t_lower_protocol(self, underlying_price: float) -> None:
        if any(s["tier"] == self.tier for s in self._satellites if s["status"] != LegState.FLAT):
            return
        self._close_satellite(self.tier - 2, "CE")
        log.info(f"T{self.tier} breach at {underlying_price}. Selling T{self.tier} call.")
        result = self.om.enter_short(underlying_price, "CE")
        if "error" in result:
            return
        self._satellites.append({
            "tier": self.tier,
            "option_type": "CE",
            "status": LegState.SHIFTED,
            "tradingsymbol": result["symbol"],
            "instrument_token": int(result["token"]),
            "entry_price": result["price"],
            "buy_id": result["sl_id"],
            "buy_params": {
                "price": result["price"],
                "trigger_price": result["price"] + self.config.get("stop_loss", 500),
            },
        })
        self.current_premium += result["price"]
        self.bounds.append([underlying_price + self.current_premium,
                            underlying_price - self.current_premium])
        b = self.bounds[-1]
        log.info(f"T{self.tier} call sold. New bounds: [{b[1]}, {b[0]}]")

    def cleanup(self) -> None:
        log.info("Coinshort Strategy cleanup")

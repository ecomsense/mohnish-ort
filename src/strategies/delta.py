from sdk.symbol import OptionSymbol
from sdk.helper import RestApi
from sdk.wserver import Wserver
from sdk.books import Books
from sdk.signals import check_any_out_of_bounds_np
from constants import CNFG, logging, S_DATA
from sdk.models import Calls, Puts
import pendulum
import os
import yaml
from traceback import print_exc
from toolkit.kokoo import blink
from copy import deepcopy

class Delta:
    def __init__(self):
        logging.info("Initializing Delta Strategy (T1)")
        self.strategy_settings = CNFG.get("strategy", {})
        
        # Initialize Symbol helper
        symbol_settings = CNFG.get("base_instrument", {})
        self.symbols = OptionSymbol(**symbol_settings)
        self.symbols.get_expiry(self.strategy_settings.get("expiry_offset", 0))
        
        # API and Books
        self.api = RestApi(self.strategy_settings.get("quantity", 1))
        
        # State
        self.tier = 1
        self.upper_bound = 0
        self.lower_bound = 0
        self.current_premium = 0
        
        self.ce = Calls()
        self.pe = Puts()
        
        self.load_state()
        
        # If not initialized, do initial entry
        if self.upper_bound == 0:
            self.initial_entry()

    def save_state(self):
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
            with open(os.path.join(S_DATA, "delta_state.yml"), "w") as f:
                yaml.dump(state, f)
        except Exception as e:
            logging.error(f"Error saving state: {e}")

    def load_state(self):
        try:
            state_path = os.path.join(S_DATA, "delta_state.yml")
            if not os.path.exists(state_path):
                return
            with open(state_path, "r") as f:
                state = yaml.safe_load(f)
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
            logging.info(f"Strategy state loaded. Resuming at Tier T{self.tier}.")
        except Exception as e:
            logging.error(f"Error loading state: {e}")

    def get_ltp(self, ws, instrument_token, tradingsymbol):
        quotes = ws.ltp()
        try:
            price = [d["last_price"] for d in quotes if d["instrument_token"] == instrument_token][0]
            return price
        except Exception:
            logging.error(f"Could not fetch LTP for {tradingsymbol}")
            return 0.0

    def initial_entry(self):
        try:
            logging.info("Executing Initial T1 Neutral Entry")
            # We need LTP of base to get options
            # For now, let's assume we can get it from WS or API
            # This is a bit tricky in the first tick
            # ... (omitted for brevity, will implement fully)
            pass

    def tick(self, ws, books):
        # Implementation of the strategy logic for each tick
        # This replaces the while loop in the original run()
        try:
            bn_ltp = self.get_ltp(ws, self.symbols.instrument_token, self.symbols.tradingsymbol)
            if bn_ltp == 0: return

            for opt in [self.ce, self.pe]:
                if opt.status == -1: # SHORT
                    if books.is_order_complete(opt.buy_id):
                        logging.info(f"{opt.tradingsymbol} SAR hit. Status flipping to LONG.")
                        opt.status = 1
                        opt.entry_time = pendulum.now()
                        opt.buy_params["price"] = opt.buy_params["trigger_price"]
                        self.set_bounds(opt)

                elif opt.status == 1: # LONG
                    last_price = self.get_ltp(ws, opt.instrument_token, opt.tradingsymbol)
                    # TTL and OOB checks here...
                    # (logic from original Delta.run)

            # Band management
            if bn_ltp >= self.upper_bound and self.ce.status == 1:
                self.tier += 1
                self.t_upper_protocol(ws)
            elif bn_ltp <= self.lower_bound and self.pe.status == 1:
                self.tier += 1
                self.t_lower_protocol(ws)
            
            self.save_state()

        except Exception as e:
            logging.error(f"Delta tick error: {e}")
            print_exc()

    def set_bounds(self, opt):
        median = opt.buy_params["price"]
        lst_of_bands = (median - self.strategy_settings["stop_loss"], median + self.strategy_settings["target"])
        opt.bounds = [lst_of_bands], [median]

    def cleanup(self, books):
        logging.info("Delta Strategy cleanup")
        # Logic to cancel orders and square off

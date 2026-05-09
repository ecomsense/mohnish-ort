from integrations.api import Helper
from core.models import Calls, Puts, Options
from engine.signals import (
    check_any_out_of_bounds_np,
)
from engine.symbols import Symbols
from integrations.wsocket import Wsocket
from core.utils import retry_until_not_none
from traceback import print_exc
from toolkit.kokoo import blink, is_time_past, timer
from copy import deepcopy
from core.config import load_symbols
import pendulum

class Delta:
    def __init__(self, config, symbol_settings, logging):
        self.config = config
        self.logging = logging
        strategy_settings = config.strategy
        self.symbols = Symbols(logging, **symbol_settings)
        self.quantity = strategy_settings["quantity"]
        self.stop_loss = strategy_settings["stop_loss"]
        self.target = strategy_settings["target"]
        self.ttl = strategy_settings.get("ttl")
        self.slippage = strategy_settings.get("slippage", 0.5)
        self.help = Helper(self.quantity, config, logging)
        
        self.ce = Calls()
        self.pe = Puts()
        
        # Action Zones Management
        self.tier = 1 # T1, T2, T3...
        self.upper_bound = 0
        self.lower_bound = 0
        self.current_premium = 0
        
        self.logging.info("Initializing Delta Strategy (T1)")
        d_symbol = load_symbols()
        self.ws = Wsocket(config, d_symbol, logging, self.help)
        self.quotes = False
        while not self.quotes or not any(self.quotes):
            self.quotes = self.ws.ltp()

        self.logging.debug("decipher ltp from websocket response")
        bn_ltp = self.ltp_from_ws_response(
            [self.symbols.instrument_token, self.symbols.tradingsymbol]
        )
        tokens = self.symbols.build_chain(bn_ltp, full_chain=True)
        self.quotes = self.ws.ltp(tokens)

        if not self.load_state():
            self.initial_entry()

    def save_state(self):
        try:
            from core.config import S_DATA
            import yaml
            import os

            def to_dict(opt):
                d = deepcopy(vars(opt))
                if d.get("entry_time"):
                    d["entry_time"] = d["entry_time"].isoformat()
                return d

            state = {
                "tier": self.tier,
                "upper_bound": self.upper_bound,
                "lower_bound": self.lower_bound,
                "current_premium": self.current_premium,
                "ce": to_dict(self.ce),
                "pe": to_dict(self.pe)
            }
            
            os.makedirs(S_DATA, exist_ok=True)
            state_path = os.path.join(S_DATA, "delta_state.yml")
            with open(state_path, "w") as f:
                yaml.dump(state, f)
            self.logging.debug(f"Strategy state saved to {state_path}")
        except Exception as e:
            self.logging.error(f"Error saving state: {e}")

    def load_state(self):
        try:
            from core.config import S_DATA
            import yaml
            import os
            state_path = os.path.join(S_DATA, "delta_state.yml")
            if not os.path.exists(state_path):
                return False

            with open(state_path, "r") as f:
                state = yaml.safe_load(f)
            
            if not state:
                return False

            self.tier = state.get("tier", 1)
            self.upper_bound = state.get("upper_bound", 0)
            self.lower_bound = state.get("lower_bound", 0)
            self.current_premium = state.get("current_premium", 0)

            def from_dict(opt, data):
                for k, v in data.items():
                    if k == "entry_time" and v:
                        v = pendulum.parse(v)
                    setattr(opt, k, v)

            from_dict(self.ce, state.get("ce", {}))
            from_dict(self.pe, state.get("pe", {}))

            self.logging.info(f"Strategy state loaded. Resuming at Tier T{self.tier}.")
            return True
        except Exception as e:
            self.logging.error(f"Error loading state: {e}")
            return False

    @retry_until_not_none
    def ltp_from_ws_response(self, lst):
        try:
            self.quotes = self.ws.ltp()
            last_price = [
                d["last_price"] for d in self.quotes if d["instrument_token"] == lst[0]
            ][0]
            if last_price is None:
                raise Exception("price is None")
            return last_price
        except Exception as e:
            self.logging.error(f"ltp error: {e}")
            # print_exc()

    def initial_entry(self):
        try:
            self.logging.info("Executing Initial T1 Neutral Entry")
            bn_ltp = self.ltp_from_ws_response(
                [self.symbols.instrument_token, self.symbols.tradingsymbol]
            )
            
            ce_symbol, pe_symbol = self.symbols.get_option_symbols(bn_ltp)
            
            # Setup CE & PE
            self.ce.tradingsymbol = ce_symbol
            self.ce.instrument_token = self.symbols.tokens_from_symbols(ce_symbol)[0]["instrument_token"]
            ce_price = self.ltp_from_ws_response([self.ce.instrument_token, self.ce.tradingsymbol])
            
            self.pe.tradingsymbol = pe_symbol
            self.pe.instrument_token = self.symbols.tokens_from_symbols(pe_symbol)[0]["instrument_token"]
            pe_price = self.ltp_from_ws_response([self.pe.instrument_token, self.pe.tradingsymbol])
            
            # Define Action Zones based on total premium
            self.current_premium = ce_price + pe_price
            self.set_action_zones(bn_ltp, self.current_premium)

            # Sell both legs
            for opt in [self.ce, self.pe]:
                self.short(opt)
                opt.status = -1
            self.save_state()
                
        except Exception as e:
            self.logging.error(f"initial_entry error: {e}")
            print_exc()

    def set_action_zones(self, base_price, premium):
        self.upper_bound = base_price + premium
        self.lower_bound = base_price - premium
        self.logging.info(f"Action Zones Updated (Tier T{self.tier}): [{self.lower_bound}, {self.upper_bound}] based on Premium: {premium}")
        self.save_state()

    def short(self, option):
        try:
            last_price = self.ltp_from_ws_response([option.instrument_token, option.tradingsymbol])
            params = {
                "symbol": option.tradingsymbol,
                "side": "SELL",
                "order_type": "MARKET",
                "last_price": last_price,
            }
            option.short_id = self.help.enter(params)
            option.short_params = deepcopy(params)
            option.status = -1
            
            params["side"] = "BUY"
            params["order_type"] = "SL"
            params["quantity"] = self.quantity * 2
            params["trigger_price"] = params["last_price"] + self.stop_loss
            params["price"] = params["trigger_price"] + self.slippage
            params["tag"] = "stoploss"
            option.buy_id = self.help.enter(params)
            option.buy_params = params
            self.save_state()
            
        except Exception as e:
            self.logging.error(f"short error: {e}")
            print_exc()

    def is_order_complete(self, subset):
        try:
            def is_subset(S, H):
                for key, value in S.items():
                    if key not in H or H[key] != value:
                        return False
                return True

            for dct in self.orders:
                if is_subset(subset, dct):
                    return True
        except Exception as e:
            self.logging.info(f"is_order_complete error: {e}")
        return False

    def set_bounds_to_check(self, opt):
        median = opt.buy_params["price"]
        self.logging.info(f"price for target and stop calculation is {median}")
        lst_of_bands = (median - self.stop_loss, median + self.target)
        opt.bounds = [lst_of_bands], [median]
        self.logging.info(f"setting bounds {str(lst_of_bands)}")

    def run(self):
        try:
            while not is_time_past(self.config.program.stop):
                self.orders = self.help.api().orders
                self.quotes = self.ws.ltp()
                bn_ltp = self.ltp_from_ws_response([self.symbols.instrument_token, self.symbols.tradingsymbol])

                for opt in [self.ce, self.pe]:
                    if opt.status == -1:
                        subset = {"order_id": opt.buy_id, "status": "COMPLETE"}
                        if self.is_order_complete(subset):
                            self.logging.info(f"{opt.tradingsymbol} hit stop loss. SAR to Long.")
                            opt.status = 1
                            opt.entry_time = pendulum.now()
                            opt.buy_params["price"] = opt.buy_params["trigger_price"]
                            self.set_bounds_to_check(opt)
                            self.save_state()

                    elif opt.status == 1:
                        last_price = self.ltp_from_ws_response([opt.instrument_token, opt.tradingsymbol])
                        
                        if self.ttl and opt.entry_time:
                            minutes_in_trade = (pendulum.now() - opt.entry_time).in_minutes()
                            if minutes_in_trade >= self.ttl:
                                if last_price > opt.buy_params["price"]:
                                    self.logging.info(f"TTL {minutes_in_trade}m exceeded for {opt.tradingsymbol} in profit. Exiting.")
                                    self.exit_to_neutral(opt)
                                    continue

                        opt.bounds = opt.bounds[0], [last_price]
                        if check_any_out_of_bounds_np(opt.bounds):
                            sl_level, target_level = opt.bounds[0][-1]
                            
                            if last_price >= target_level:
                                self.logging.info(f"{opt.tradingsymbol} hit profit target ({target_level}). Shifting strike.")
                                self.shift_strike(opt)
                            elif last_price <= sl_level:
                                self.logging.info(f"{opt.tradingsymbol} hit stop loss ({sl_level}). SAR back to Short.")
                                self.exit_to_neutral(opt)
                                self.short(opt)
                                opt.status = -1
                            continue

                if bn_ltp >= self.upper_bound:
                    if self.ce.status == 1:
                        self.tier += 1
                        self.logging.info(f"Reached T{self.tier} (Upper). Executing Protocol.")
                        self.t_upper_protocol()
                        self.save_state()
                elif bn_ltp <= self.lower_bound:
                    if self.pe.status == 1:
                        self.tier += 1
                        self.logging.info(f"Reached T-{self.tier} (Lower). Executing Protocol.")
                        self.t_lower_protocol()
                        self.save_state()

                blink()
            else:
                self.logging.info("Program stop time reached. Closing all.")
                self.cleanup()

        except Exception as e:
            self.logging.error(f"run error: {e}")
            print_exc()
            timer(5)
            self.run()

    def t_upper_protocol(self):
        # Shift Put side UP
        if self.pe.status != 0:
            self.exit_to_neutral(self.pe)
        
        bn_ltp = self.ltp_from_ws_response([self.symbols.instrument_token, self.symbols.tradingsymbol])
        _, pe_symbol = self.symbols.get_option_symbols(bn_ltp)
        self.pe.tradingsymbol = pe_symbol
        self.pe.instrument_token = self.symbols.tokens_from_symbols(pe_symbol)[0]["instrument_token"]
        
        # Sell MARKET (collect new premium)
        pe_price = self.ltp_from_ws_response([self.pe.instrument_token, self.pe.tradingsymbol])
        params = {"symbol": self.pe.tradingsymbol, "side": "SELL", "order_type": "MARKET", "last_price": pe_price}
        self.pe.short_id = self.help.enter(params)
        
        # Get Call price to determine NEW range
        ce_price = self.ltp_from_ws_response([self.ce.instrument_token, self.ce.tradingsymbol])
        self.current_premium = ce_price + pe_price
        self.set_action_zones(bn_ltp, self.current_premium)

        # SL only for T2+ Puts
        params["side"] = "BUY"; params["order_type"] = "SL"; params["quantity"] = self.quantity
        params["trigger_price"] = params["last_price"] + self.stop_loss
        params["price"] = params["trigger_price"] + self.slippage
        params["tag"] = "stoploss_no_sar"
        self.pe.buy_id = self.help.enter(params)
        self.pe.status = -1
        self.save_state()

    def t_lower_protocol(self):
        # Shift Call side DOWN
        if self.ce.status != 0:
            self.exit_to_neutral(self.ce)
        
        bn_ltp = self.ltp_from_ws_response([self.symbols.instrument_token, self.symbols.tradingsymbol])
        ce_symbol, _ = self.symbols.get_option_symbols(bn_ltp)
        self.ce.tradingsymbol = ce_symbol
        self.ce.instrument_token = self.symbols.tokens_from_symbols(ce_symbol)[0]["instrument_token"]
        
        ce_price = self.ltp_from_ws_response([self.ce.instrument_token, self.ce.tradingsymbol])
        params = {"symbol": self.ce.tradingsymbol, "side": "SELL", "order_type": "MARKET", "last_price": ce_price}
        self.ce.short_id = self.help.enter(params)
        
        pe_price = self.ltp_from_ws_response([self.pe.instrument_token, self.pe.tradingsymbol])
        self.current_premium = ce_price + pe_price
        self.set_action_zones(bn_ltp, self.current_premium)

        params["side"] = "BUY"; params["order_type"] = "SL"; params["quantity"] = self.quantity
        params["trigger_price"] = params["last_price"] + self.stop_loss
        params["price"] = params["trigger_price"] + self.slippage
        params["tag"] = "stoploss_no_sar"
        self.ce.buy_id = self.help.enter(params)
        self.ce.status = -1
        self.save_state()

    def shift_strike(self, opt):
        self.exit_to_neutral(opt)
        bn_ltp = self.ltp_from_ws_response([self.symbols.instrument_token, self.symbols.tradingsymbol])
        
        # Case Study: Sell the ATM strike at the target price (treated as ITM in spec)
        self.short(opt)
        opt.status = -1 

        # Interlock: If one side becomes SHORT, disable other side
        if isinstance(opt, Calls):
            self.logging.info("Call is now SHORT. Disabling Put side (Short-Side Interlock).")
            if self.pe.status != 0: self.exit_to_neutral(self.pe)
        else:
            self.logging.info("Put is now SHORT. Disabling Call side (Short-Side Interlock).")
            if self.ce.status != 0: self.exit_to_neutral(self.ce)
        self.save_state()

    def exit_to_neutral(self, opt):
        last_price = self.ltp_from_ws_response([opt.instrument_token, opt.tradingsymbol])
        params = {
            "symbol": opt.tradingsymbol,
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": self.quantity,
            "last_price": last_price,
            "tag": "exit"
        }
        self.help.enter(params)
        opt.status = 0
        self.save_state()

    def cleanup(self):
        try:
            lst_of_orders = self.help.api().orders
            for order in lst_of_orders:
                if order["status"] in ["OPEN", "TRIGGER PENDING", None]:
                    params = dict(order_id=order["order_id"], variety=order["variety"])
                    self.help.api().order_cancel(**params)
            
            lst_of_pos = self.help.api().positions
            for pos in lst_of_pos:
                if pos["quantity"] != 0:
                    side = "SELL" if pos["quantity"] > 0 else "BUY"
                    # Find token for this symbol
                    instrument_token = self.symbols.tokens_from_symbols(pos["symbol"])[0]["instrument_token"]
                    last_price = self.ltp_from_ws_response([instrument_token, pos["symbol"]])
                    args = dict(
                        symbol=pos["symbol"],
                        side=side,
                        order_type="MARKET",
                        tag="exit",
                        last_price=last_price,
                    )
                    self.help.enter(args)
        except Exception as e:
            self.logging.error(f"cleanup error: {e}")

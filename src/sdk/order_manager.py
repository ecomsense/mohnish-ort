from broker_ai.delta.wsocket import Wsocket
from broker_ai.delta.symbols import Symbol
from sdk.restapi import Restapi
from sdk.models import LegState
from constants import get_logger
import pendulum

log = get_logger(__name__)

class OrderManager:
    def __init__(self, ws: Wsocket, symbols: Symbol, api: Restapi, config: dict) -> None:
        self.ws = ws
        self.symbols = symbols
        self.api = api
        self.config = config
        self._subscribed: set[str] = set()

    @property
    def quantity(self) -> int:
        return self.config.get("quantity", 1)

    @property
    def stop_loss(self) -> float:
        return self.config["stop_loss"]

    @property
    def target(self) -> float:
        return self.config["target"]

    @property
    def slippage(self) -> float:
        return self.config.get("slippage", 0.5)

    def _subscribe(self, token: str) -> None:
        if token not in self._subscribed:
            self._subscribed.add(token)
            self.ws.subscribe([token])

    def _get_price(self, token: str) -> float:
        return self.ws.ltp.get(token, 0.0)

    def _resolve_option(self, underlying_price: float, option_type: str, distance: int = 0) -> dict:
        rows = self.symbols.filter_by_moneyness(underlying_price, distance, option_type)
        if not rows:
            raise ValueError(f"No symbol found for {option_type} at {underlying_price}")
        return rows[0]

    def enter_short(self, underlying_price: float, option_type: str) -> dict:
        row = self._resolve_option(underlying_price, option_type)
        token = row["ws_token"]
        symbol = row["tradingsymbol"]
        self._subscribe(token)
        price = self._get_price(token)
        if price == 0.0:
            log.warning(f"No LTP yet for {symbol}, using last known")
            return {"error": "no_quote"}
        short_id = self.api.enter({
            "symbol": symbol,
            "side": "SELL",
            "order_type": "MARKET",
            "last_price": price,
        })
        sl_id = self.api.enter({
            "symbol": symbol,
            "side": "BUY",
            "order_type": "SL",
            "quantity": self.quantity * 2,
            "last_price": price,
            "trigger_price": price + self.stop_loss,
            "price": price + self.stop_loss + self.slippage,
            "tag": "stoploss",
        })
        result = {
            "symbol": symbol,
            "token": token,
            "strike": row["strike"],
            "price": price,
            "short_id": short_id,
            "sl_id": sl_id,
        }
        log.info(f"Entered short {symbol} @ {price}")
        return result

    def exit_position(self, token: str, symbol: str) -> None:
        price = self._get_price(token)
        if price == 0.0:
            log.warning(f"No LTP for exit {symbol}")
            return
        self.api.enter({
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": self.quantity,
            "last_price": price,
            "tag": "exit",
        })
        log.info(f"Exited {symbol} @ {price}")

    def is_order_complete(self, order_id: str) -> bool:
        done = {"COMPLETE", "FILLED"}
        for o in self.api.api().orders:
            if o.get("order_id") == order_id and o.get("status") in done:
                return True
        return False

    def manage_leg(self, opt, underlying_price: float) -> None:
        opt_price = self.ws.ltp.get(str(opt.instrument_token), 0.0)
        if opt.status == LegState.SHORT:
            if self.is_order_complete(opt.buy_id):
                log.info(f"{opt.tradingsymbol} SAR hit. Flipping to LONG.")
                entry_price = opt.buy_params.get("trigger_price", 0) or 0
                if entry_price == 0:
                    return
                opt.status = LegState.LONG
                opt.entry_time = pendulum.now()
                opt.buy_params["price"] = entry_price
                opt.buy_params["target"] = entry_price + self.target
                sl_id = self.api.enter({
                    "symbol": opt.tradingsymbol,
                    "side": "SELL",
                    "order_type": "SL",
                    "quantity": self.quantity,
                    "last_price": entry_price,
                    "trigger_price": entry_price - self.stop_loss,
                    "price": entry_price - self.stop_loss - self.slippage,
                    "tag": "stoploss_long",
                })
                opt.buy_id = sl_id
        elif opt.status == LegState.LONG:
            target = opt.buy_params.get("target")
            if target and opt_price >= target:
                log.info(f"{opt.tradingsymbol} target {target} hit at {opt_price}. Shifting strike.")
                self.api.api().order_modify(order_id=opt.buy_id, order_type="MARKET", price=0.0, quantity=self.quantity)
                option_type = "CE" if isinstance(opt, __import__("sdk.models", fromlist=["Calls"]).Calls) else "PE"
                result = self.enter_short(underlying_price, option_type)
                if "error" not in result:
                    opt.tradingsymbol = result["symbol"]
                    opt.instrument_token = int(result["token"])
                    opt.short_id = result["short_id"]
                    opt.buy_id = result["sl_id"]
                    opt.status = LegState.SHORT
                    opt.entry_time = None
                    opt.buy_params = {
                        "price": result["price"],
                        "trigger_price": result["price"] + self.stop_loss,
                    }
                return
            ttl = self.config.get("ttl", 0)
            if ttl and opt.entry_time:
                mins = (pendulum.now() - opt.entry_time).in_minutes()
                if mins >= ttl and opt_price > opt.buy_params.get("price", 0):
                    log.info(f"{opt.tradingsymbol} TTL {ttl}m exceeded. Shifting strike.")
                    self.api.api().order_modify(order_id=opt.buy_id, order_type="MARKET", price=0.0, quantity=self.quantity)
                    option_type = "CE" if isinstance(opt, __import__("sdk.models", fromlist=["Calls"]).Calls) else "PE"
                    result = self.enter_short(underlying_price, option_type)
                    if "error" not in result:
                        opt.tradingsymbol = result["symbol"]
                        opt.instrument_token = int(result["token"])
                        opt.short_id = result["short_id"]
                        opt.buy_id = result["sl_id"]
                        opt.status = LegState.SHORT
                        opt.entry_time = None
                        opt.buy_params = {
                            "price": result["price"],
                            "trigger_price": result["price"] + self.stop_loss,
                        }
                    return
            if self.is_order_complete(opt.buy_id):
                log.info(f"{opt.tradingsymbol} SAR hit. Flipping to SHORT.")
                entry_price = opt.buy_params.get("trigger_price", 0) or 0
                if entry_price == 0:
                    return
                opt.status = LegState.SHORT
                opt.buy_params.pop("target", None)
                opt.entry_time = pendulum.now()
                opt.buy_params["price"] = entry_price
                option_type = "CE" if isinstance(opt, __import__("sdk.models", fromlist=["Calls"]).Calls) else "PE"
                result = self.enter_short(underlying_price, option_type)
                if "error" not in result:
                    opt.tradingsymbol = result["symbol"]
                    opt.instrument_token = int(result["token"])
                    opt.short_id = result["short_id"]
                    opt.buy_id = result["sl_id"]
                    opt.buy_params = {
                        "price": result["price"],
                        "trigger_price": result["price"] + self.stop_loss,
                    }
        elif opt.status == LegState.FLAT:
            pass

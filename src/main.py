from constants import O_SETG, logging
from symbols import dump, dict_from_yml
from symbols import Symbols
from wsocket import Wsocket
from api import Helper
from traceback import print_exc
from toolkit.kokoo import timer, is_time_past
import pendulum as pdlm


SUPPORT_RESISTANCE_LEVELS = {
    "BANKNIFTY": [28000, 30000, 32000, 36000, 38000, 40000],
    "HDFC": [1900, 2000, 2100, 2600, 2700, 2800],
    "ICICI": [520, 540, 560, 700, 720, 740],
    "SBI": [320, 340, 360, 500, 520, 540],
    "AXIS": [620, 640, 660, 800, 820, 840],
}


class TradingStrategy:
    def __init__(self, settings):
        # Unpack settings into instance attributes
        self.base = settings.get("base", "BANKNIFTY")  # Provide a default value if needed
        self.initial_quantity = settings.get("quantity", 15)
        self.stop_loss = settings.get("stop_loss", 60)
        self.expiry_offset = settings.get("expiry_offset", 0)

        self.orders = []
        self.current_prices = {}
        self.ws = Wsocket()
        self.api = Helper(self.initial_quantity)

    def ltp_from_ws_response(self, instrument_token, resp):
        bn_ltp = [
            d["last_price"] for d in resp if d["instrument_token"] == instrument_token
        ][0]
        return bn_ltp


    def take_initial_entry(self, bn_ltp):
        ce_symbol, pe_symbol = self.symbols.get_option_symbols(bn_ltp)
        params = {
            "symbol": ce_symbol,
            "side": "SELL",
            "order_type": "MARKET",
            "ltp": bn_ltp,
        }
        self.orders.append(self.api.enter(params))
        params["symbol"] = pe_symbol
        params["ltp"] = bn_ltp
        self.orders.append(self.api.enter(params))
        logging.info("Initial entry complete")

    def monitor_positions(self):
        while True:
            resp = self.ws.ltp()
            print(f"Positions {self.orders}")
            for position in self.orders:
                current_price = self.ltp_from_ws_response(position["token"], resp)
                self.current_prices[position["token"]] = current_price
                if (
                    position["side"] == "SELL"
                    and current_price >= position["entry_price"] + self.stop_loss
                ):
                    self.handle_stop_loss(position, current_price)
                elif (
                    position["side"] == "BUY"
                    and current_price <= position["entry_price"] - self.stop_loss
                ):
                    self.handle_stop_loss(position, current_price)
            timer(1)

    def handle_stop_loss(self, position, current_price):
        self.note_down_prices()
        self.exit_position(position)
        if not self.check_support_resistance_levels():
            self.reenter_position(position)

    def note_down_prices(self):
        for symbol in SUPPORT_RESISTANCE_LEVELS:
            self.current_prices[symbol] = self.ws.get_ltp(symbol)
        logging.info("Noted down current prices: %s", self.current_prices)

    def exit_position(self, position):
        self.ws.exit_position(
            position["symbol"], position["side"], position["quantity"]
        )
        logging.info("Exited position: %s", position)
        self.orders.remove(position)

    def check_support_resistance_levels(self):
        for symbol, levels in SUPPORT_RESISTANCE_LEVELS.items():
            current_price = self.current_prices[symbol]
            for i in range(0, len(levels), 2):
                support = levels[i]
                resistance = levels[i + 1] if i + 1 < len(levels) else levels[i]
                if support <= current_price < resistance:
                    next_resistance = (
                        levels[i + 1] if i + 2 < len(levels) else resistance
                    )
                    previous_support = levels[i] if i - 1 >= 0 else support
                    SUPPORT_RESISTANCE_LEVELS[symbol] = [
                        previous_support,
                        next_resistance,
                    ]
                    logging.info(
                        "Updated support and resistance levels for %s: support = %d, resistance = %d",
                        symbol,
                        previous_support,
                        next_resistance,
                    )
                    return True
        return False

    def reenter_position(self, position):
        # TODO: To implement this completely
        side = "SELL" if position["side"] == "BUY" else "BUY"
        quantity = self.initial_quantity * 2
        # TODO: get the ltp of base
        call_token, put_token = self.symbols.get_option_symbols(self.current_prices["BANKNIFTY"])
        new_token = call_token if position["symbol"].endswith("CALL") else put_token
        self.orders.append(
            self.ws.place_order("BANKNIFTY", side, "ATM", quantity, new_token)
        )
        logging.info(
            "Reentered position for %s with %d lots", position["symbol"], quantity
        )

    def run(self):
        try:
            logging.debug("subscribing index from symbols yml automtically")
            self.ws: object = Wsocket()
            resp = False
            while not resp or not any(resp):
                resp = self.ws.ltp()

            logging.debug("decipher ltp from websocket response")
            dct = dict_from_yml("base", "BANKNIFTY")
            bn_ltp = self.ltp_from_ws_response(dct["instrument_token"], resp)
            self.exchange = dct["exchange"]
            self.symbols = Symbols(**dct)
            self.expiry = self.symbols.get_expiry(expiry_offset=self.expiry_offset)
            self.take_initial_entry(bn_ltp)
            self.monitor_positions()
        except Exception as e:
            logging.error(f"run error: {e}")
            print_exc()
            __import__("sys").exit(1)


def root():
    try:
        logging.info("HAPPY TRADING")
        # download necessary masters
        dump()
        entry_time: str = O_SETG["program"]["start"]
        strategy_settings = O_SETG["strategy"]
        while not is_time_past(entry_time):
            logging.info(f"z #@! zZZ sleeping till {entry_time}")
            timer(1)
        TradingStrategy(strategy_settings).run()
    except Exception as e:
        print(f"root error: {e}")
        print_exc()


root()

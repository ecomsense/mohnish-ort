from typing import Dict, List

from kiteconnect import KiteTicker

from api import Helper
from constants import D_SYMBOL, O_CNFG, logging


def filter_ws_keys(incoming: List[Dict]):
    keys = ["instrument_token", "last_price"]
    new_lst = []
    if incoming and isinstance(incoming, list) and any(incoming):
        for dct in incoming:
            new_dct = {}
            for key in keys:
                if dct.get(key, None):
                    new_dct[key] = dct[key]
                    new_lst.append(new_dct)
    return new_lst


class Wsocket:
    def update_ticks(self, incoming_ticks):
        incoming_ticks = filter_ws_keys(incoming_ticks)

        for incoming_tick in incoming_ticks:
            instrument_token = incoming_tick.get("instrument_token")
            found = False

            for tick in self.ticks:
                if tick.get("instrument_token") == instrument_token:
                    # Update the existing tick's last price
                    tick["last_price"] = incoming_tick.get("last_price")
                    found = True
                    break

            if not found:
                # If no existing tick is found, add the new tick
                self.ticks.append(incoming_tick)

    def __init__(self):
        self.ticks = []
        # Subscribe to a list of instrument_tokens (Index first).
        nse_symbols = D_SYMBOL["NSE"]
        self.tokens = [v for k, v in nse_symbols.items() if k == "instrument_token"]
        kite = Helper.api().kite
        if O_CNFG["broker"] == "bypass":
            logging.debug("using BYPASS ticker")
            self.kws = kite.kws()
        else:
            logging.debug("using official ticker")
            self.kws = KiteTicker(kite.api_key, kite.access_token)
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close
        self.kws.on_error = self.on_error
        self.kws.on_reconnect = self.on_reconnect
        self.kws.on_noreconnect = self.on_noreconnect

        # Infinite loop on the main thread. Nothing after this will run.
        # You have to use the pre-defined callbacks to manage subscriptions.
        self.kws.connect(threaded=True)

    def ltp(self, tokens=None):
        if tokens:
            tokens = [dct["instrument_token"] for dct in tokens]
            self.tokens = list(set(self.tokens + tokens))
        return self.ticks

    def on_ticks(self, ws, ticks):
        # print(ticks)
        if self.tokens is not None:
            ws.subscribe(self.tokens)
        self.update_ticks(ticks)

    def on_connect(self, ws, response):
        if response:
            print(f"on connect: {response}")
        ws.subscribe(self.tokens)
        # Set RELIANCE to tick in `full` mode.
        ws.set_mode(ws.MODE_LTP, self.tokens)

    def on_close(self, ws, code, reason):
        # On connection close stop the main loop
        # Reconnection will not happen after executing `ws.stop()`
        ws.stop()

    def on_error(self, ws, code, reason):
        # Callback when connection closed with error.
        logging.info(
            "Connection error: {code} - {reason}".format(code=code, reason=reason)
        )

    def on_reconnect(self, ws, attempts_count):
        # Callback when reconnect is on progress
        logging.info("Reconnecting: {}".format(attempts_count))

    # Callback when all reconnect failed (exhausted max retries)

    def on_noreconnect(self, ws):
        logging.info("Reconnect failed.")

from constants import D_SYMBOL, logging
from api import Helper


class Wsocket:
    def __init__(self):
        self.ticks = []
        self.tokens = []
        self.kws = Helper.api().kite.kws()
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close
        self.kws.on_error = self.on_error
        self.kws.on_reconnect = self.on_reconnect
        self.kws.on_noreconnect = self.on_noreconnect

        # Infinite loop on the main thread. Nothing after this will run.
        # You have to use the pre-defined callbacks to manage subscriptions.
        self.kws.connect(threaded=True)

    def ltp(self, tokens):
        if any(tokens):
            self.tokens = [v for k, v in tokens.items() if k == "instrument_token"]
        return self.ticks

    def on_ticks(self, ws, response):
        print(response)
        if any(self.tokens):
            ws.subscribe(self.tokens)
            self.tokens = []
        if response:
            dct = {str(res["instrument_token"]): res["last_price"] for res in response}
            for old in self.ticks:
                token = str(old["instrument_token"])
                old["last_price"] = dct[token]
            else:
                self.ticks = response

    def on_connect(self, ws, response):
        # Callback on successful connect.
        # Subscribe to a list of instrument_tokens (RELIANCE and ACC here).
        nse_symbols = D_SYMBOL["NSE"]
        self.tokens = [v for k, v in nse_symbols.items() if k == "instrument_token"]
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

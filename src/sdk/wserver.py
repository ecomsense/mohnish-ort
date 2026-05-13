from typing import Dict, List
from kiteconnect import KiteTicker
from constants import CNFG, logging
from sdk.helper import RestApi

class Wserver:
    def __init__(self, d_symbol=None):
        self.ticks = []
        self._ltp = []
        self.tokens = []
        if d_symbol:
            self.set_tokens(d_symbol)
            
        broker_obj = RestApi.api()
        broker = CNFG.get("broker", "bypass")
        
        if broker == "delta-india":
            logging.debug("using broker-ai (delta-india) ticker")
            self.kws = broker_obj.ticker()
        elif broker == "bypass":
            logging.debug("using BYPASS ticker")
            self.kws = broker_obj.kite.kws()
        else:
            logging.debug("using official ticker")
            kite = broker_obj.kite
            self.kws = KiteTicker(kite.api_key, kite.access_token)
            
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close
        self.kws.on_error = self.on_error
        self.kws.on_reconnect = self.on_reconnect
        self.kws.on_noreconnect = self.on_noreconnect

        self.kws.connect(threaded=True)

    def set_tokens(self, d_symbol):
        self.tokens = []
        for k, v in d_symbol.items():
            if k != "exchanges" and isinstance(v, dict) and "instrument_token" in v:
                self.tokens.append(v["instrument_token"])

    def update_ticks(self, incoming_ticks):
        if not incoming_ticks:
            return
            
        for incoming_tick in incoming_ticks:
            instrument_token = incoming_tick.get("instrument_token")
            if not instrument_token:
                continue
                
            found = False
            for tick in self._ltp:
                if tick.get("instrument_token") == instrument_token:
                    tick["last_price"] = incoming_tick.get("last_price")
                    found = True
                    break

            if not found:
                self._ltp.append({
                    "instrument_token": instrument_token,
                    "last_price": incoming_tick.get("last_price")
                })

    def ltp(self, tokens=None):
        if tokens:
            if isinstance(tokens, list):
                if isinstance(tokens[0], dict):
                    tokens = [dct["instrument_token"] for dct in tokens]
                self.tokens = list(set(self.tokens + tokens))
        self.update_ticks(self.ticks)
        return self._ltp

    def on_ticks(self, ws, ticks):
        if self.tokens:
            ws.subscribe(self.tokens)
        self.ticks = ticks

    def on_connect(self, ws, response):
        logging.info(f"Wserver connected: {response}")
        if self.tokens:
            ws.subscribe(self.tokens)
            ws.set_mode(ws.MODE_LTP, self.tokens)

    def on_close(self, ws, code, reason):
        logging.error(f"Wserver closed: {code} - {reason}")

    def on_error(self, ws, code, reason):
        logging.error(f"Wserver error: {code} - {reason}")

    def on_reconnect(self, ws, attempts_count):
        logging.warning(f"Wserver reconnecting: {attempts_count}")

    def on_noreconnect(self, ws):
        logging.error("Wserver reconnect failed.")

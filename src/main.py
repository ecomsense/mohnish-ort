from constants import logging, D_SYMBOL
from symbols import dump, build_chain
from wsocket import Wsocket
from typing import Dict
from types import SimpleNamespace
from traceback import print_exc
from time import sleep


def ltp_from_ws_response(exchange, tradingsymbol, resp):
    # get instrument token from symbol dictionaries
    bn_token = [
        d["instrument_token"]
        for k, d in D_SYMBOL.items()
        if k == exchange and d["tradingsymbol"] == tradingsymbol
    ][0]
    #  get ltp for banknifty from wsocket response
    bn_ltp = [d["last_price"] for d in resp if d["instrument_token"] == bn_token][0]
    print(tradingsymbol, bn_ltp)
    return bn_ltp


def root():
    try:
        logging.info("HAPPY TRADING")
        # download necessary masters
        dump()

        # subscribing from yml files automtically
        ws: object = Wsocket()
        resp = False
        while not resp:
            resp = ws.ltp([])
        else:
            print(resp)
            bn_ltp = ltp_from_ws_response("NSE", "NIFTY BANK", resp)

        # then use it to find atm and option chain
        if bn_ltp:
            lst = build_chain("BANKNIFTY", "24JUL")
            print(lst)
            # we are subscribing now only for options
            resp = ws.ltp(lst)
            print(resp)

        # TODO for demo can be removed
        while True:
            # we should get the option prices here
            resp = ws.ltp([])
            sleep(10)

        """
        # we create a namespace so that dictionaries values
        # can be accessed like properties
        tasks = SimpleNamespace(
            ws=ws,
            oc=oc,
            sr=sr,
        )
        """

    except Exception as e:
        print(e)
        print_exc()


if __name__ == "__main__":
    root()

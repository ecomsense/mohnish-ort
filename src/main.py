from constants import logging, D_SYMBOL
from symbols import dump, build_chain
from wsocket import Wsocket
from typing import Dict
from types import SimpleNamespace
from traceback import print_exc


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

        # TODO  wsocket should be initiated without params
        ws: object = Wsocket()
        resp = False
        while not resp:
            resp = ws.ltp([])
        else:
            print(resp)
            bn_ltp = ltp_from_ws_response("NSE", "NIFTY BANK", resp)

        # TO DO
        # get ltp for indices and update the dict_of_symbol_token
        # then use it to find atm and option chain
        #
        if bn_ltp:
            lst = build_chain("NSE", "BANKNIFTY", "24JUL")
            print(lst)
            pass

        """
        # passing token should provide the ltp of underlying banknifty
        ltp = ws.ltp(["NSE|###"])

        # update the ltps

        # initialize symbol object
        # use symbol class from symbols.py to get tradingsymbols as a list
        symbol: object = Symbol(O_SETG["exchange"], O_SETG["symbol"], O_SETG["expiry"])
        atm = symbol.calc_atm_from_ltp(ltp)
        oc: Dict = symbol.build_option_chain(atm)

        # dictionary should contain token and SR levels
        sr: Dict = universe.main()

        # we create a namespace so that dictionaries values
        # can be accessed like properties
        tasks = SimpleNamespace(
            ws=ws,
            symbol=symbol,
            oc=oc,
            sr=sr,
        )
        """

    except Exception as e:
        print(e)
        print_exc()


if __name__ == "__main__":
    root()

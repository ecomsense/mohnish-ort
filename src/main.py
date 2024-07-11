from constants import logging
from symbols import dump, dict_from_yml
from symbols import Symbols
from wsocket import Wsocket
from typing import Dict
from types import SimpleNamespace
from traceback import print_exc
from time import sleep


def ltp_from_ws_response(instrument_token, resp):
    bn_ltp = [
        d["last_price"] for d in resp if d["instrument_token"] == instrument_token
    ][0]
    print(bn_ltp)
    return bn_ltp


def root():
    try:
        logging.info("HAPPY TRADING")
        # download necessary masters
        dump()

        # TODO
        # move this to strategy ?

        # subscribing index from symbols.yml automtically
        ws: object = Wsocket()
        resp = False
        #  wait for index to give ltp
        while not resp:
            resp = ws.ltp()

        # extract a dictionary from symbol yml, given the key, value
        dct = dict_from_yml("base", "BANKNIFTY")
        # decipher ltp from instrument token
        bn_ltp = ltp_from_ws_response(dct["instrument_token"], resp)

        # then use it to find atm and option chain
        if bn_ltp:
            bn = Symbols(**dct)
            lst = bn.build_chain("24JUL", bn_ltp)
            # we are subscribing now only for options
            resp = ws.ltp(lst)

        # TODO for demo can be removed
        while True:
            # we should get the option prices here
            resp = ws.ltp()
            print(resp)
            sleep(1)

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


root()

from constants import logging, O_SETG
from symbols import dump
from wsocket import Wsocket
from typing import Dict
from types import SimpleNamespace
from traceback import print_exc


def main():
    try:
        logging.info("HAPPY TRADING")
        dict_of_symbol_token = dump()

        """
        # TODO  wsocket should be initiated without params
        # ws: object = Wsocket()
        """
        for k, v in dict_of_symbol_token["NSE"].items():
            print(k, v)
            # TO DO
            # get ltp for indices and update the dict_of_symbol_token
            # then use it to find atm and option chain

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


main()

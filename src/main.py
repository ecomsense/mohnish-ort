from constants import logging, O_SETG
from wsocket import Wsocket
import universe
from symbols import Symbol
from typing import Dict
from types import SimpleNamespace
from traceback import print_exc


def do(task):
    raise NotImplementedError


def run(tasks):
    """
    repetitive tasks that will
    run again and again
    """
    while True:
        tasks.oc.update(tasks.ws.ltp(list(tasks.oc.keys())))
        for task in tasks:
            do(task)


def main():
    try:
        logging.info("HAPPY TRADING")
        """
        description:
            initialize singletons here
            also consume globals if any here
        """
        # initialize websocket
        ws: object = Wsocket(O_SETG["kite"], O_SETG["sym_tkn"])
        # passing token should provide the ltp of underlying banknifty
        ltp = ws.ltp(["NSE|###"])

        # initialize symbol object
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
        while O_SETG["start"]:
            run(tasks)

    except Exception as e:
        print(e)
        print_exc()


main()

import datetime
from constants import logging
from symbols import dump, dict_from_yml
from symbols import Symbols
from wsocket import Wsocket
from api import Helper, build_order
from typing import Dict
from types import SimpleNamespace
from traceback import print_exc
from time import sleep

SUPPORT_RESISTANCE_LEVELS = {
    'BANKNIFTY': [28000, 30000, 32000, 36000, 38000, 40000],
    'HDFC': [1900, 2000, 2100, 2600, 2700, 2800],
    'ICICI': [520, 540, 560, 700, 720, 740],
    'SBI': [320, 340, 360, 500, 520, 540],
    'AXIS': [620, 640, 660, 800, 820, 840]
}

class TradingStrategy:
    def __init__(self, entry_time: str, initial_quantity: int, stop_loss: int, reentries: int):
        self.entry_time = entry_time
        self.initial_quantity = initial_quantity
        self.stop_loss = stop_loss
        self.reentries = reentries
        self.positions = []
        self.current_prices = {}
        self.ws = Wsocket()
        self.api = Helper()
        # self.initialize_logging()

    def initialize_logging(self):
        logging.basicConfig(filename='trading_strategy.log', level=logging.INFO, format='%(asctime)s - %(message)s')

    def get_current_time(self):
        return datetime.datetime.now().strftime('%H:%M:%S')

    def wait_until_entry_time(self):
        while self.get_current_time() < self.entry_time:
            sleep(1)

    def ltp_from_ws_response(self, instrument_token, resp):
        bn_ltp = [d["last_price"] for d in resp if d["instrument_token"] == instrument_token][0]
        return bn_ltp

    def get_atm_strike(self, bn_ltp):
        atm_strike = round(bn_ltp / 100) * 100
        print(f"ATM strike: {atm_strike}")
        return atm_strike

    def get_option_tokens(self, bn, atm_strike, expiry_date):

        straddle = bn.get_straddle("24JUL", atm_strike)
        # Using lambda and filter to get the tokens for the specific strike
        ce_symbol = next(filter(lambda x: x['instrument_type'] == 'CE' and x['strike'] == atm_strike, straddle), {}).get('tradingsymbol')
        pe_symbol = next(filter(lambda x: x['instrument_type'] == 'PE' and x['strike'] == atm_strike, straddle), {}).get('tradingsymbol')
        print(f"ce_token, pe_token : {ce_symbol, pe_symbol}")
        return ce_symbol, pe_symbol

    def take_initial_entry(self, bn, bn_ltp):
        atm_strike = self.get_atm_strike(bn_ltp)
        ce_symbol, pe_symbol = self.get_option_tokens(bn, atm_strike, "24JUL")
        ce_order = build_order(self.exchange, ce_symbol, 'SELL', self.initial_quantity)
        pe_order = build_order(self.exchange, pe_symbol, 'SELL', self.initial_quantity)
        self.positions.append(self.api.enter('SELL', [ce_order]))
        self.positions.append(self.api.enter('SELL', [pe_order]))
        logging.info("Initial entry taken at %s", self.get_current_time())

    def monitor_positions(self):
        while True:
            resp = self.ws.ltp()
            print(f"Positions {self.positions}")
            for position in self.positions:
                current_price = self.ltp_from_ws_response(position['token'], resp)
                self.current_prices[position['token']] = current_price
                if position['side'] == 'SELL' and current_price >= position['entry_price'] + self.stop_loss:
                    self.handle_stop_loss(position, current_price)
                elif position['side'] == 'BUY' and current_price <= position['entry_price'] - self.stop_loss:
                    self.handle_stop_loss(position, current_price)
            sleep(1)

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
        self.ws.exit_position(position['symbol'], position['side'], position['quantity'])
        logging.info("Exited position: %s", position)
        self.positions.remove(position)

    def check_support_resistance_levels(self):
        for symbol, levels in SUPPORT_RESISTANCE_LEVELS.items():
            current_price = self.current_prices[symbol]
            for i in range(0, len(levels), 2):
                support = levels[i]
                resistance = levels[i + 1] if i + 1 < len(levels) else levels[i]
                if support <= current_price < resistance:
                    next_resistance = levels[i + 1] if i + 2 < len(levels) else resistance
                    previous_support = levels[i] if i - 1 >= 0 else support
                    SUPPORT_RESISTANCE_LEVELS[symbol] = [previous_support, next_resistance]
                    logging.info("Updated support and resistance levels for %s: support = %d, resistance = %d", 
                                 symbol, previous_support, next_resistance)
                    return True
        return False

    def reenter_position(self, position):
        side = 'SELL' if position['side'] == 'BUY' else 'BUY'
        quantity = self.initial_quantity * 2
        atm_strike = self.get_atm_strike(self.current_prices['BANKNIFTY'])
        call_token, put_token = self.get_option_tokens(Symbols(), atm_strike, "24JUL")
        new_token = call_token if position['symbol'].endswith('CALL') else put_token
        self.positions.append(self.ws.place_order('BANKNIFTY', side, 'ATM', quantity, new_token))
        logging.info("Reentered position for %s with %d lots", position['symbol'], quantity)

    def run(self):
        self.wait_until_entry_time()
        dump()
        # subscribing index from symbols.yml automtically
        self.ws: object = Wsocket()
        resp = False
        #  wait for index to give ltp
        while not resp:
            resp = self.ws.ltp()
        dct = dict_from_yml("base", "BANKNIFTY")
        # decipher ltp from instrument token
        bn_ltp = self.ltp_from_ws_response(dct["instrument_token"], self.ws.ltp())

        # Get the exchange
        self.exchange = dct["exchange"]
        
        if bn_ltp:
            bn = Symbols(**dct)
            self.take_initial_entry(bn, bn_ltp)
            self.monitor_positions()

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
        # if bn_ltp:
        #     bn = Symbols(**dct)
        #     # lst = bn.build_chain("24JUL", bn_ltp)
        #     # we are subscribing now only for options
        #     # resp = ws.ltp(lst)
        #     # print("lst:", lst)
        #     straddle = bn.get_straddle("24JUL", bn_ltp)
        #     print("straddle:", straddle)

        # TODO for demo can be removed
        # while True:
        #     # we should get the option prices here
        #     resp = ws.ltp()
        #     # print(resp)
        #     sleep(1)

        strategy = TradingStrategy(entry_time="09:30:00", initial_quantity=1, stop_loss=60, reentries=1)
        strategy.run()

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

from broker_ai.delta.wsocket import Wsocket
from constants import get_logger
from toolkit.kokoo import blink
import traceback

log = get_logger(__name__)

class Engine:
    def __init__(self, strategy, ws: Wsocket,
                 underlying_token: str) -> None:
        self.strategy = strategy
        self.ws = ws
        self._token = underlying_token
        self.ws.on_connect = self._on_reconnect

    def _on_reconnect(self) -> None:
        self.ws.subscribe([self._token])
        self.strategy._resubscribe_tokens()

    def run(self) -> None:
        log.info("Engine started")
        self.ws.subscribe([self._token])

        try:
            while True:
                price = self.ws.ltp.get(self._token, 0.0)
                try:
                    self.strategy.tick(price)
                except Exception as e:
                    log.error(f"Strategy tick error: {e}")
                    traceback.print_exc()
                blink()
        except KeyboardInterrupt:
            log.info("Shutdown requested. Cleaning up.")
            self.strategy.cleanup()
        except Exception as e:
            log.error(f"Engine run error: {e}")
            traceback.print_exc()

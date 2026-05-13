from broker_ai.delta.wsocket import Wsocket
from constants import get_logger
from toolkit.kokoo import is_time_past, blink
import traceback

log = get_logger(__name__)

class Engine:
    def __init__(self, strategies: list, ws: Wsocket,
                 subscribe_tokens: list[str], stop_time: str) -> None:
        self.strategies = strategies
        self.ws = ws
        self._tokens = subscribe_tokens
        self._stop = stop_time
        self.ws.on_connect = self._on_reconnect

    def _on_reconnect(self) -> None:
        if self._tokens:
            self.ws.subscribe(self._tokens)

    def run(self) -> None:
        log.info("Engine started")
        if self._tokens:
            self.ws.subscribe(self._tokens)

        try:
            while not is_time_past(self._stop):
                for strategy in self.strategies:
                    try:
                        strategy.tick(self.ws)
                    except Exception as e:
                        log.error(f"Error in strategy tick: {e}")
                        traceback.print_exc()
                blink()

            log.info("Stop time reached. Cleaning up.")
            for strategy in self.strategies:
                strategy.cleanup()

        except Exception as e:
            log.error(f"Engine run error: {e}")
            traceback.print_exc()

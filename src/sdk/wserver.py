from typing import Any
from broker_ai.delta.wsocket import Wsocket as DeltaWsocket
from constants import get_logger, CNFG

log = get_logger(__name__)


class Wserver:
    def __init__(self, d_symbol: dict[str, Any] | None = None) -> None:
        api_key = CNFG.get("api_key")
        api_secret = CNFG.get("secret")
        self._ws = DeltaWsocket(api_key=api_key, api_secret=api_secret)
        self._tokens: list[str] = []
        if d_symbol:
            self._set_tokens(d_symbol)

        self._ws.on_connect = self._on_connect
        self._ws.on_ticks = self._on_ticks
        self._ws.on_close = self._on_close
        self._ws.on_error = self._on_error

        self._ws.connect(threaded=True)

    def _set_tokens(self, d_symbol: dict[str, Any]) -> None:
        for k, v in d_symbol.items():
            if k != "exchanges" and isinstance(v, dict) and "instrument_token" in v:
                self._tokens.append(str(v["instrument_token"]))

    def ltp(self, tokens: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if tokens:
            raw = [d.get("instrument_token") or d for d in tokens]
            self._tokens = list(set(self._tokens + [str(t) for t in raw]))
            self._ws.subscribe(self._tokens)
        return [
            {"instrument_token": int(k), "last_price": v}
            for k, v in self._ws.ltp.items()
        ]

    def _on_connect(self) -> None:
        log.info("Wserver connected")
        if self._tokens:
            self._ws.subscribe(self._tokens)

    def _on_ticks(self, ltp: dict) -> None:
        pass

    def _on_close(self) -> None:
        log.error("Wserver closed")

    def _on_error(self, err: str) -> None:
        log.error(f"Wserver error: {err}")

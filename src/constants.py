from os import path
from toolkit.fileutils import Fileutils
from toolkit.async_logger import AsyncLogger
import logging as _logging
import yaml

O_FUTL = Fileutils()
S_DATA = "../data/"
S_LOG = S_DATA + "log.txt"
S_FACTORY = "../factory/"
S_SETTINGS = S_FACTORY + "settings.yml"
S_SYMBOLS = S_FACTORY + "symbols.yml"

def ensure_paths():
    if not O_FUTL.is_file_exists(S_LOG):
        print("creating data dir")
        O_FUTL.add_path(S_LOG)

def load_yml(file_path: str) -> dict:
    if not path.exists(file_path):
        return {}
    with open(file_path, "r") as f:
        return yaml.safe_load(f) or {}

def get_credentials() -> dict:
    parent = path.dirname(path.abspath(__file__))
    grand_parent = path.dirname(parent)
    folder_name = path.basename(grand_parent)
    cred_file_name = "-".join(reversed(folder_name.split("_"))) + ".yml"
    cred_path = path.join(path.dirname(grand_parent), cred_file_name)
    return load_yml(cred_path)

CNFG = {**load_yml(S_SETTINGS), **get_credentials()}

_log_initialized = False

def init_logging() -> None:
    global _log_initialized
    _log_cfg = CNFG.get("log", {})
    level = _log_cfg.get("level", _logging.INFO)
    show = _log_cfg.get("show", True)
    _logger = AsyncLogger(
        level=level,
        log_file=None if show else S_LOG,
        use_journal=False,
    )
    _logger.start()
    if _logger._listener is None:
        raise RuntimeError("AsyncLogger failed to start - app cannot continue")
    _log_initialized = True

def get_logger(name: str | None = None) -> _logging.Logger:
    if not _log_initialized:
        raise RuntimeError("init_logging() must be called before get_logger()")
    return _logging.getLogger(name)

import os
from toolkit.fileutils import Fileutils
from toolkit.async_logger import AsyncLogger
import logging as _logging
import yaml

O_FUTL = Fileutils()
S_DATA = "../data/"
S_LOG = S_DATA + "log.txt"
S_FACTORY = "../factory/"
S_SETTINGS = S_DATA + "settings.yml"
S_SYMBOLS = S_DATA + "symbols.yml"

def ensure_paths():
    if not O_FUTL.is_file_exists(S_LOG):
        print("creating data dir")
        O_FUTL.add_path(S_LOG)
    for name in ("settings.yml", "symbols.yml"):
        dst = S_DATA + name
        if not O_FUTL.is_file_exists(dst):
            O_FUTL.copy_file(source_dir=S_FACTORY, destination_dir=S_DATA, filename=name)

def load_yml(file_path: str) -> dict:
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r") as f:
        return yaml.safe_load(f) or {}

def get_credentials() -> dict:
    parent = os.path.dirname(os.path.abspath(__file__))
    grand_parent = os.path.dirname(parent)
    folder_name = os.path.basename(grand_parent)
    cred_file_name = "-".join(reversed(folder_name.split("_"))) + ".yml"
    cred_path = os.path.join(os.path.dirname(grand_parent), cred_file_name)
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

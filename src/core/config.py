from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import yaml
from os import path
from traceback import print_exc
from toolkit.fileutils import Fileutils
from toolkit.logger import Logger

O_FUTL = Fileutils()
S_DATA = "../data/"
S_LOG = S_DATA + "log.txt"

class LogConfig(BaseModel):
    show: bool = True
    level: int = 30

class ProgramConfig(BaseModel):
    start: str = "9:30"
    stop: str = "15:00"

class TradeConfig(BaseModel):
    start: str = "9:30"
    stop: str = "15:00"

class FullConfig(BaseModel):
    log: LogConfig = Field(default_factory=LogConfig)
    program: ProgramConfig = Field(default_factory=ProgramConfig)
    trade: TradeConfig = Field(default_factory=TradeConfig)
    signals: Dict[str, Any] = Field(default_factory=dict)
    strategy: Dict[str, Any] = Field(default_factory=dict)
    live: int = 0
    broker: str = "bypass"
    userid: str = ""
    password: str = ""
    totp: str = ""
    api_key: str = ""
    secret: str = ""

def ensure_paths():
    if not O_FUTL.is_file_exists(S_LOG):
        print("creating data dir")
        O_FUTL.add_path(S_LOG)
    elif O_FUTL.is_file_not_2day(S_LOG):
        O_FUTL.nuke_file(S_LOG)

def load_yml(file_path: str) -> Dict[str, Any]:
    if not path.exists(file_path):
        return {}
    with open(file_path, "r") as f:
        return yaml.safe_load(f) or {}

def get_config() -> FullConfig:
    ensure_paths()
    
    # Load credentials (mohnish-ort.yml is usually 2 levels up in current setup)
    parent = path.dirname(path.abspath(__file__))
    grand_parent = path.dirname(parent)
    folder_name = path.basename(grand_parent)
    cred_file_name = "-".join(reversed(folder_name.split("_"))) + ".yml"
    cred_path = path.join(path.dirname(grand_parent), cred_file_name)
    
    creds = load_yml(cred_path)
    settings = load_yml("../resources/settings.yml")
    
    # Merge them - settings override defaults, creds provide auth
    merged = {**settings, **creds}
    
    # Handle the nested structure of O_CNFG from legacy constants.py
    # O_CNFG = yml_to_obj() -> would return the full dict from mohnish-ort.yml
    # We need to extract broker specific info
    broker = merged.get("broker", "bypass")
    broker_creds = merged.get(broker, {})
    
    final_data = {
        **merged,
        "broker": broker,
        "userid": broker_creds.get("userid", ""),
        "password": broker_creds.get("password", ""),
        "totp": broker_creds.get("totp", ""),
        "api_key": broker_creds.get("api_key", ""),
        "secret": broker_creds.get("secret", ""),
    }
    
    return FullConfig(**final_data)

def load_symbols() -> Dict[str, Any]:
    return load_yml("../resources/symbols.yml")

def set_logger(log_cfg: LogConfig):
    try:
        if log_cfg.show:
            return Logger(log_cfg.level, S_LOG)
        return Logger(log_cfg.level)
    except Exception as e:
        print(f"set logger error: {e}")
        print_exc()
        return Logger(30)

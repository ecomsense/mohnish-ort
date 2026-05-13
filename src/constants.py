from os import path
from toolkit.fileutils import Fileutils
from toolkit.logger import Logger
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
    elif O_FUTL.is_file_not_2day(S_LOG):
        O_FUTL.nuke_file(S_LOG)

ensure_paths()

def load_yml(file_path: str):
    if not path.exists(file_path):
        return {}
    with open(file_path, "r") as f:
        return yaml.safe_load(f) or {}

# Load credentials
def get_credentials():
    parent = path.dirname(path.abspath(__file__))
    grand_parent = path.dirname(parent)
    folder_name = path.basename(grand_parent)
    cred_file_name = "-".join(reversed(folder_name.split("_"))) + ".yml"
    cred_path = path.join(path.dirname(grand_parent), cred_file_name)
    return load_yml(cred_path)

CNFG = {**load_yml(S_SETTINGS), **get_credentials()}
logging = Logger(CNFG.get("log", {}).get("level", 30), S_LOG) if CNFG.get("log", {}).get("show", True) else Logger(30)

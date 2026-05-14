import sys
import types
from unittest.mock import MagicMock

sys.path.insert(0, "src")

constants = types.ModuleType("constants")
constants.get_logger = lambda name: __import__("logging").getLogger(name)
constants.CNFG = {}
constants.S_DATA = "../data/"
constants.O_FUTL = MagicMock()
sys.modules["constants"] = constants

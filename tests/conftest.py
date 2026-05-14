import sys
import types

sys.path.insert(0, "src")

constants = types.ModuleType("constants")
constants.get_logger = lambda name: __import__("logging").getLogger(name)
constants.CNFG = {}
constants.S_DATA = "../data/"
sys.modules["constants"] = constants

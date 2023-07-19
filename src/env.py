import sys
from pathlib import Path

CONFIG_PATH = (Path.home() / ".local/share/state_dl").resolve()
PROCEDURES_DIR = CONFIG_PATH / "procedure_scripts"
sys.path.append(str(PROCEDURES_DIR))  # TODO: Better place to do this

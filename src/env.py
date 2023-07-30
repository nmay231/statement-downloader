import sys
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

CONFIG_PATH = (Path.home() / ".local/share/state_dl").resolve()
PROCEDURES_DIR = CONFIG_PATH / "procedure_scripts"
# TODO: Is this even needed?
sys.path.append(str(PROCEDURES_DIR))  # TODO: Better place to do this


class Config(BaseModel):
    procedures: dict[str, "ProcedureInfo"]
    contexts: dict[str, "ContextInfo"]


class ProcedureInfo(BaseModel):
    display_name: str


class BrowserEnum(str, Enum):
    chromium = "chromium"
    firefox = "firefox"
    webkit = "webkit"


class ContextInfo(BaseModel):
    display_name: str
    browser: BrowserEnum


# TODO: Load when the app launches?
config = Config.model_validate_json((CONFIG_PATH / "data.json").read_text())


assert __name__ != "__main__"
DEFAULT_PROCEDURE_SNIPPET = (
    Path(__file__).parent / "default_procedure_snippet.py"
).read_text()

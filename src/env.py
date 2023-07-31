import sys
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

HOME_PATH = (Path.home() / ".local/share/state_dl").resolve()
PROCEDURES_DIR = HOME_PATH / "procedure_scripts"
# TODO: Is this even needed?
sys.path.append(str(PROCEDURES_DIR))  # TODO: Better place to do this


class Config(BaseModel):
    procedures: dict[str, "ProcedureInfo"] = Field(default_factory=dict)
    contexts: dict[str, "ContextInfo"] = Field(default_factory=dict)


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
CONFIG_PATH = HOME_PATH / "data.json"
config = Config.model_validate_json(CONFIG_PATH.read_text())


assert __name__ != "__main__"
DEFAULT_PROCEDURE_SNIPPET = (
    Path(__file__).parent / "default_procedure_snippet.py"
).read_text()

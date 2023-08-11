from functools import cached_property
import sys
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Config(BaseModel):
    procedures: dict[str, "ProcedureInfo"] = Field(default_factory=dict)
    contexts: dict[str, "ContextInfo"] = Field(default_factory=dict)

    @classmethod
    def load_from_path(cls, path: Path) -> "Config":
        return cls.model_validate_json(path.read_text())

    def save_to_path(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=4))


class ProcedureInfo(BaseModel):
    display_name: str


class BrowserEnum(str, Enum):
    chromium = "chromium"
    firefox = "firefox"
    webkit = "webkit"


class ContextInfo(BaseModel):
    display_name: str
    browser: BrowserEnum


class Context:
    home_p = (Path.home() / ".local/share/state_dl").resolve()
    procedures_dir_p = home_p / "procedure_scripts"
    config_p = home_p / "data.json"

    def __init__(self, config: Config) -> None:
        self._config = config
        sys.path.append(str(self.procedures_dir_p))

    @cached_property
    def default_procedure_snippet(self):
        return (Path(__file__).parent / "default_procedure_snippet.py").read_text()

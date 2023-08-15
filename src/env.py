import sys
from enum import Enum
from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, Field


class Config(BaseModel):
    procedures: dict[str, "ProcedureInfoConfigOnly"] = Field(default_factory=dict)
    contexts: dict[str, "ContextInfo"] = Field(default_factory=dict)

    @classmethod
    def load_from_path(cls, path: Path) -> "Config":
        return cls.model_validate_json(path.read_text())

    def save_to_path(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=4))


class ProcedureInfoConfigOnly(BaseModel):
    ...


class ProcedureInfo(ProcedureInfoConfigOnly):
    """Runtime version that has more information"""

    name: str
    "Both the filename and display name"
    exists: bool
    "Whether the file exists or not"

    @staticmethod
    def from_proc(
        _proc: ProcedureInfoConfigOnly, *, name: str, exists: bool
    ) -> "ProcedureInfo":
        return ProcedureInfo(name=name, exists=exists)


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

        existing_procs = {proc.stem: proc for proc in self.procedures_dir_p.glob("*.py")}
        if untracked := existing_procs.keys() - self._config.procedures.keys():
            for proc_name in untracked:
                # When there is more data about a procedure, like which browser context to use,
                # I will use the defaults and have the name say it's <UNTRACKED> or something
                self._config.procedures[proc_name] = ProcedureInfoConfigOnly()
            self._config.save_to_path(self.config_p)

        self.all_procedures = dict[str, ProcedureInfo]()
        missing_files = self._config.procedures.keys() - existing_procs.keys()
        for name, proc in self._config.procedures.items():
            self.all_procedures[name] = ProcedureInfo.from_proc(
                proc,
                name=name,
                exists=name not in missing_files,
            )

    @cached_property
    def default_procedure_snippet(self):
        return (Path(__file__).parent / "default_procedure_snippet.py").read_text()

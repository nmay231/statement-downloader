import sys
from enum import Enum
from functools import cached_property
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


class ProcedureInfoExt(ProcedureInfo):
    """Runtime version that also knows whether the procedure file exists"""

    exists: bool

    @staticmethod
    def from_proc(proc: ProcedureInfo, *, exists: bool) -> "ProcedureInfoExt":
        return ProcedureInfoExt(display_name=proc.display_name, exists=exists)


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
                # If there is eventually more data to a procedure than its name, I can add a
                # temp default and have the name say it's <UNTRACKED> or something
                self._config.procedures[proc_name] = ProcedureInfo(display_name=proc_name)
            self._config.save_to_path(self.config_p)

        self.all_procedures = dict[str, ProcedureInfoExt]()
        missing_files = self._config.procedures.keys() - existing_procs.keys()
        for name, proc in self._config.procedures.items():
            self.all_procedures[name] = ProcedureInfoExt.from_proc(
                proc,
                exists=name not in missing_files,
            )

    @cached_property
    def default_procedure_snippet(self):
        return (Path(__file__).parent / "default_procedure_snippet.py").read_text()

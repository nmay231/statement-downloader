import os
import sys
from datetime import datetime
from enum import Enum
from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, Field


class Config(BaseModel):
    edit_file: str | None = None
    """Command to edit file in the format `/path/to/editor --optional-params "{file}"`
    (the `"{file}"` is literal and filled at runtime)"""
    editor_in_terminal: bool = True
    "Does the editor take control of the terminal (e.g. vim)"
    contexts: dict[str, "ContextInfo"] = Field(default_factory=dict)
    "Browser contexts (cookies, localStorage, etc.)"
    procedures: dict[str, "ProcedureInfoConfigOnly"] = Field(default_factory=dict)
    "User procedures"

    @classmethod
    def load_from_path(cls, path: Path) -> "Config":
        # TODO: Provide defaults if file doesn't exist?
        return cls.model_validate_json(path.read_text())

    def save_to_path(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=4))


class ProcedureInfoConfigOnly(BaseModel):
    snapshots: list["Snapshot"]
    "A list of snapshots a user can quickly switch between while developing"


class ProcedureInfo(ProcedureInfoConfigOnly):
    """Runtime version that has more information"""

    name: str
    "Both the filename and display name"

    @staticmethod
    def from_proc(proc: ProcedureInfoConfigOnly, *, name: str) -> "ProcedureInfo":
        return ProcedureInfo(name=name, snapshots=proc.snapshots)

    def exists(self, ctx: "Context") -> bool:
        """True if the procedure file exists"""
        return (ctx.procedures_dir_p / f"{self.name}.py").exists()


class Snapshot(BaseModel):
    uri: str
    "A url or sometimes a uri with `file://` schema to point to a local snapshot of the site"
    # TODO: would time.delta be better?
    time: datetime = Field(default_factory=datetime.now)
    "An approximate time the snapshot was taken. Mostly for the user's reference."

    @property
    def file_name(self) -> Path | None:
        """Return the file path if the uri uses the `file://` schema. None otherwise."""
        if self.uri.startswith("file://"):
            return Path(self.uri[7:])


class ContextInfo(BaseModel):
    display_name: str
    browser: "BrowserEnum"


class BrowserEnum(str, Enum):
    chromium = "chromium"
    firefox = "firefox"
    webkit = "webkit"


class Context:
    home_p = (Path.home() / ".local/share/state_dl").resolve()
    procedures_dir_p = home_p / "procedure_scripts"
    config_p = home_p / "data.json"

    def __init__(self, config: Config) -> None:
        self._config = config
        sys.path.append(str(self.procedures_dir_p))

        self.editor_in_terminal = config.editor_in_terminal

        if self._config.edit_file:
            self.edit_file = self._config.edit_file
        else:
            editor = os.environ["VISUAL"] or os.environ["EDITOR"] or "/bin/nano"
            self.edit_file = editor + ' "{file}"'

        save_to_disk = False

        existing_procs = {proc.stem: proc for proc in self.procedures_dir_p.glob("*.py")}
        if untracked := existing_procs.keys() - self._config.procedures.keys():
            save_to_disk = True
            for proc_name in untracked:
                # When there is more data about a procedure, like which browser context to use,
                # I will use the defaults and have the name say it's <UNTRACKED> or something
                self._config.procedures[proc_name] = ProcedureInfoConfigOnly(snapshots=[])

        self.all_procedures = dict[str, ProcedureInfo]()
        for name, proc in self._config.procedures.items():
            # TODO: Technically, there is also the issue where a file exists that is not
            # TODO: tracked by the config (similar to procedure files), but that is less
            # TODO: of a concern here since the directory will probably be deleted anyways
            len_before_filter = len(proc.snapshots)
            proc.snapshots = [
                snap
                for snap in proc.snapshots
                # Filter out static snapshots that no longer exist
                if snap.file_name is None or snap.file_name.exists()
            ]
            self.all_procedures[name] = ProcedureInfo.from_proc(proc, name=name)
            save_to_disk = save_to_disk or len_before_filter > len(proc.snapshots)

        if save_to_disk:
            self._config.save_to_path(self.config_p)

    @cached_property
    def default_procedure_snippet(self):
        return (Path(__file__).parent / "default_procedure_snippet.py").read_text()

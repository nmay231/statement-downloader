import importlib
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import ModuleType

from textual import on
from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    OptionList,
    SelectionList,
    Static,
)
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from ..browser import BrowserWrapper
from ..env import DEFAULT_PROCEDURE_SNIPPET, PROCEDURES_DIR, ProcedureInfo
from ..widgets.editor import Editor
from .snapshot_new_procedure import Snapshot, SnapshotNewProcedure


class TODOBetterErrorName(Exception):
    ...


# TODO: Add a submit button and .dismiss(procedure_info)
class EditProcedure(Screen[ProcedureInfo]):  # type: ignore Pylance hates this for some reason..
    # TODO: How to share browser without stepping on each other's toes?
    _browser: BrowserWrapper | None = None

    def __init__(
        self,
        proc_name: str,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        *,
        snapshot=False,
    ) -> None:
        super().__init__(name, id, classes)
        self.to_snapshot = snapshot
        self.snapshots = dict[str, Snapshot]()
        self.snapshot_dir = Path(tempfile.gettempdir())

        if not proc_name:
            raise TODOBetterErrorName
        self.procedure_file = PROCEDURES_DIR / f"{proc_name}.py"
        if not self.procedure_file.exists():
            self.procedure_file.write_text(DEFAULT_PROCEDURE_SNIPPET)

    def on_mount(self):
        if self.to_snapshot:
            self.app.push_screen(SnapshotNewProcedure(), self.receive_snapshots)

    def receive_snapshots(self, snapshots: list[Snapshot]) -> None:
        self.snapshots = {str(index): snap for index, snap in enumerate(snapshots)}
        for id, snap in self.snapshots.items():
            self.snapshot_list.add_option(Option(snap.url, id=id))
            # TODO: File permissions so random things cannot access it.
            path = self.snapshot_dir / f"{id}.html"
            path.write_text(snap.html_content)

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="editor"):
            self.editor = Editor(self.procedure_file.read_text(), "python")
            yield self.editor
        with ScrollableContainer(id="misc"):
            self.snapshot_list = OptionList(id="snapshot_list")
            yield self.snapshot_list
            with Widget(classes="button-row"):
                yield Button("Run `find()`", id="find")
                yield Button("Run `many()` TODO", id="many")
                yield Button("Save procedure", id="save")
            self.name_label = Static("<PROCEDURE_NAME>")
            yield self.name_label
            self.options = SelectionList()
            yield self.options
        with ScrollableContainer(id="debug_output") as container:
            container.border_title = "Debug Output (stdout/stderr)"
            self.output = Static()
            yield self.output

    @on(OptionList.OptionSelected, "#snapshot_list")
    async def snapshot_list_selected(self, selected: OptionList.OptionSelected) -> None:
        if selected.option_id not in self.snapshots:
            raise KeyError
        path = self.snapshot_dir / f"{selected.option_id}.html"
        await self.browser_visit(f"file://{path}")

    async def browser_visit(self, uri: str) -> None:
        if self._browser is not None:
            await self._browser.page.goto(uri)
            return
        self._browser = BrowserWrapper()
        self._browser.context.on("close", self._clear_browser)
        await self._browser.start(uri)

    def _clear_browser(self, closed_browser):
        self._browser = None

    @on(Button.Pressed, "#find")
    async def run_find(self):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            try:
                # TODO: Timeout to catch infinite loops
                await self._run_find()
            except Exception:
                traceback.print_exc()
        output.seek(0)
        self.output.update(output.read())

    @on(Button.Pressed, "#save")
    async def save_procedure(self):
        self.procedure_file.write_text(self.editor.text)
        self.dismiss(ProcedureInfo(display_name=self.procedure_file.stem))

    async def _run_find(self):
        self.procedure_file.parent.mkdir(parents=True, exist_ok=True)
        self.procedure_file.write_text(self.editor.text)

        module = self._latest_module()
        # TODO: Bug report: https://github.com/Textualize/textual/issues/3052
        self.name_label.update(f"{self.procedure_file.stem} <PENDING>")

        if not self._browser:
            self._browser = BrowserWrapper()
            await self._browser.start(None)

        browser = self._browser.context
        page = self._browser.page
        self.options.clear_options()
        entries = await module.find(browser, page)
        assert isinstance(entries, list)
        self.options.add_options(
            [
                Selection(entry.label, entry.id, not index)
                for index, entry in enumerate(entries)
            ]
        )
        self.name_label.update(self.procedure_file.stem)

    def _latest_module(self) -> ModuleType:
        module_name = self.procedure_file.stem
        package = PROCEDURES_DIR.stem
        module = sys.modules.get(module_name)

        if not module:
            return importlib.import_module(name=module_name, package=package)
        else:
            return importlib.reload(module)

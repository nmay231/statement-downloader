import importlib
import os
import sys
import tempfile
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from subprocess import call as sh_run
from types import ModuleType
from typing import Iterator

from rich.syntax import Syntax
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button,
    ContentSwitcher,
    Footer,
    Input,
    OptionList,
    SelectionList,
    Static,
)
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from .browser import BrowserWrapper
from .env import PROCEDURES_DIR, ProcedureInfo, config


@dataclass
class Snapshot:
    url: str
    html_content: str
    time: datetime


# TODO
class TODOBetterErrorType(Exception):
    ...


class SnapshotNewProcedure(Screen[list[Snapshot]]):
    snapshots: list[Snapshot]
    browser: BrowserWrapper | None = None

    def compose(self) -> ComposeResult:
        self.snapshots = []
        with ContentSwitcher(initial="start") as self.switch:
            with Container(id="start"):
                yield Static("Press <Enter> to launch browser")
                yield Input(placeholder="Initial URL", id="url_input")
            with Container(id="snapshots"):
                yield Button("Take Snapshot", id="new_snapshot")
                self.snapshot_list = Container(id="snapshot_list")
                yield self.snapshot_list
                yield Button("Stop", id="stop_snapshot")

    @on(Button.Pressed, "#new_snapshot")
    async def new_snapshot(self):
        if not self.browser:
            raise TODOBetterErrorType
        snap = Snapshot(
            self.browser.page.url,
            await self.browser.page.content(),
            datetime.now(),
        )
        self.snapshots.append(snap)
        horizontal = Horizontal(Static(snap.url), Static(snap.time.isoformat()))
        horizontal.styles.height = 1
        self.snapshot_list.mount(horizontal)

    @on(Button.Pressed, "#stop_snapshot")
    def stop_snapshot(self):
        self.dismiss(result=self.snapshots)

    @on(Input.Submitted, "#url_input")
    async def start_snapshots(self):
        url = self.query_one("#url_input", Input).value
        self.switch.current = "snapshots"
        self.query_one("#new_snapshot", Button).focus()
        self.browser = BrowserWrapper()
        await self.browser.start(url)
        await self.new_snapshot()  # The user most likely wants to keep the first page

    async def on_unmount(self):
        if self.browser:
            await self.browser.cleanup()


assert __name__ != "__main__"
DEFAULT_PROCEDURE_SNIPPET = (
    Path(__file__).parent / "default_procedure_snippet.py"
).read_text()


# TODO: Add a submit button and .dismiss(procedure_info)
class NewProcedure(Screen[ProcedureInfo]):
    # TODO: How to share browser without stepping on each other's toes?
    _browser: BrowserWrapper | None = None
    module: ModuleType | None = None

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        /,
        # procedure_name: str | None = None,
        snapshot=False,
    ) -> None:
        super().__init__(name, id, classes)
        self.to_snapshot = snapshot
        self.snapshots = dict[str, Snapshot]()
        self.snapshot_dir = Path(tempfile.gettempdir())
        # TODO: Very hacky
        # count = len(glob.glob(str(PROCEDURES_DIR)))
        count = 0
        self.procedure_file = PROCEDURES_DIR / f"m{count}.py"
        self.procedure_file = PROCEDURES_DIR / "0test with spaces.py"
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
        # TODO: Keep what's there until I have a better testing setup
        with ScrollableContainer(id="editor"):
            self.editor = Editor(self.procedure_file.read_text(), "python")
            # self.editor = Editor(DEFAULT_PROCEDURE_SNIPPET, "python")
            yield self.editor
        with ScrollableContainer(id="misc"):
            self.snapshot_list = OptionList(id="snapshot_list")
            yield self.snapshot_list
            yield Button("Run `find()`", id="find")
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

    def _clear_browser(self, browser):
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

    async def _run_find(self):
        self.procedure_file.parent.mkdir(parents=True, exist_ok=True)
        self.procedure_file.write_text(self.editor.text)

        # TODO: Since an imported module technically is cached, and we can import more than one module, I might need to keep track of all imported modules, not just the current one, so I don't get any out of date cache hits
        # I can check if the module name is in sys.modules and if it is then reload it
        if self.module:
            importlib.reload(self.module)
        else:
            self.module = importlib.import_module(
                name=self.procedure_file.stem,
                package=PROCEDURES_DIR.stem,
            )
        # TODO: Figure out how to flush updates so this actually works halfway through this function
        self.name_label.update(f"{self.module.PROCEDURE_NAME} <PENDING>")
        self.name_label.refresh()

        if not self._browser:
            self._browser = BrowserWrapper()
            await self._browser.start(None)

        browser = self._browser.context
        page = self._browser.page
        self.options.clear_options()
        entries = await self.module.find(browser, page)
        assert isinstance(entries, list)
        self.options.add_options(
            [
                Selection(entry.label, entry.id, not index)
                for index, entry in enumerate(entries)
            ]
        )
        self.name_label.update(self.module.PROCEDURE_NAME)


class Editor(ScrollableContainer, can_focus=True):
    BINDINGS = [
        Binding("enter", "edit", "Edit text"),
    ]

    def __init__(
        self,
        text: str,
        lexer: str,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.text = text
        self.lexer = lexer
        self.editor = Static(id="editor")
        self.editor.border_title = "PROCEDURE NAME?"

    def compose(self) -> ComposeResult:
        self._update_editor()
        yield self.editor
        yield Static("<EOF>", id="eof")

    def on_click(self):
        self.action_edit()

    def action_edit(self):
        with suspend_app(self.app):
            self.text = edit_file(contents=self.text)
        self._update_editor()

    def _update_editor(self):
        self.editor.styles.height = 1 + self.text.count("\n")
        self.editor.update(Syntax(self.text, lexer=self.lexer))


def edit_file(*, contents: str, suffix=".py") -> str:
    # I feel this there's a better way to write then read from a tempfile, but whatever...
    with tempfile.NamedTemporaryFile(suffix=suffix, mode="w+") as f:
        f.write(contents)
        f.flush()
        editor = os.environ["VISUAL"] or os.environ["EDITOR"]
        sh_run([editor, f.name])
        f.seek(0)
        return f.read()


# Details: https://github.com/Textualize/textual/issues/1093
# https://github.com/Textualize/textual/pull/1150
@contextmanager
def suspend_app(app: App) -> Iterator[None]:
    driver = app._driver

    if driver is not None:
        driver.stop_application_mode()
        with redirect_stdout(sys.stdout), redirect_stderr(sys.stderr):
            yield
            driver.start_application_mode()


class MyApp(App):
    TITLE = "Browser Task Automaton"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
    ]
    CSS_PATH = ["app.tcss"]

    procedures = dict[str, ProcedureInfo | None]()

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Button("New procedure", id="to_new_procedure")
            yield Button("Snapshot before new procedure", id="to_snapshot_new_procedure")
            self.edit_procedure_button = Button(
                "Edit procedure", id="edit_procedure", disabled=True
            )
            yield self.edit_procedure_button
        self.procedure_list = OptionList(id="procedure_list")
        yield self.procedure_list
        yield Footer()  # TODO: Footer needs to be on all relevant screens

    def on_mount(self):
        self._load_procedures()

    def _load_procedures(self):
        self.procedure_list.clear_options()
        all_procedures = {**config.procedures}

        for procedure in PROCEDURES_DIR.glob("*.py"):
            name = procedure.stem
            proc = all_procedures.pop(name, None)
            self.procedures[name] = proc

            if proc is None:
                self.procedure_list.add_option(
                    Option(f"{name}.py <Untracked Procedure!>", id=name)
                )
            else:
                self.procedure_list.add_option(Option(proc.display_name, id=name))

        for name, procedure in all_procedures.items():
            self.procedures[name] = procedure
            self.procedure_list.add_option(Option(f"{name} <File missing!>", id=None))

    @on(Button.Pressed, "#to_new_procedure")
    def to_new_procedure(self):
        self.push_screen(NewProcedure(snapshot=False))

    @on(Button.Pressed, "#to_snapshot_new_procedure")
    def to_snapshot_new_procedure(self):
        self.push_screen(NewProcedure(snapshot=True))

    @on(OptionList.OptionSelected, "#procedure_list")
    async def snapshot_list_selected(self, selected: OptionList.OptionSelected) -> None:
        self.current_proc_name = selected.option_id  # I hate this...
        print("OPTION", selected.option_id)
        if selected.option_id is None:
            self.edit_procedure_button.disabled = True
            return
        assert selected.option_id in self.procedures, "Forgot to update self.procedures"
        self.edit_procedure_button.disabled = not (self.procedures.get(selected.option_id))

    @on(Button.Pressed, "#edit_procedure")
    async def edit_procedure(self) -> None:
        name = self.current_proc_name
        assert name and name in self.procedures, "Forgot to update self.procedures or procname"

        # TODO: Make NewProcedure => EditProcedure
        # self.push_screen(NewProcedure(procedure_name=name))

import importlib
import os
import sys
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import call as sh_run
from types import ModuleType
from typing import Iterator

from rich.syntax import Syntax
from rich.text import Text, TextType
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.reactive import reactive
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
from .env import PROCEDURES_DIR


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


@dataclass
class TODOProcedure:
    ...


class NewProcedure(Screen[TODOProcedure]):
    # TODO: How to share browser without stepping on each other's toes?
    _browser: BrowserWrapper | None = None
    module: ModuleType | None = None

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        /,
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
        self.editor = CollapsibleEditor(
            self.procedure_file.read_text(), "python", label="Show code"
        )
        # self.editor = CollapsibleEditor(DEFAULT_PROCEDURE_SNIPPET, "python", label="Show code")
        yield self.editor
        self.snapshot_list = OptionList(id="snapshot_list")
        yield self.snapshot_list
        yield Button("Run `find()`", id="find")
        self.name_label = Static("<PROCEDURE_NAME>")
        yield self.name_label
        self.options = SelectionList()
        yield self.options

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
        try:
            await self._run_find()
        except Exception as e:
            self.name_label.update(f"Error raise! {e!r}")
            return

    async def _run_find(self):
        self.procedure_file.parent.mkdir(parents=True, exist_ok=True)
        self.procedure_file.write_text(self.editor.text)

        if self.module:
            importlib.reload(self.module)
        else:
            self.module = importlib.import_module(
                name=self.procedure_file.stem,
                package=PROCEDURES_DIR.stem,
            )
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


class CollapsibleEditor(Static, can_focus=True):
    BINDINGS = [
        Binding("space", "toggle", "Toggle code preview"),
        Binding("enter", "edit", "Edit text"),
    ]
    DEFAULT_CSS = """
    CollapsibleEditor #label {
        background: $panel;
        color: $text;
        text-style: bold;
    }

    CollapsibleEditor:focus #label {
        color: $text 100%; # TODO: This line needed bc of a bug
        text-style: bold reverse;
    }

    #editor {
        display: none;
    }

    .open #editor {
        display: block;
    }
    """

    expanded = reactive(False)

    def __init__(
        self,
        text: str,
        lexer: str,
        *,
        label: TextType,
        expanded: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.text = text
        self.label_text = label
        self.lexer = lexer
        self.label = Static(id="label")
        self.editor = Static(id="editor")
        self.expanded = expanded  # Set after setting .label

    def compose(self) -> ComposeResult:
        self._update_editor()
        yield self.label
        yield self.editor

    def watch_expanded(self):
        caret = "v" if self.expanded else ">"
        self.label.update(Text.assemble(self.label_text, " ", caret))

        if self.expanded:
            self.add_class("open")
        else:
            self.remove_class("open")

    def action_toggle(self):
        self.expanded = not self.expanded

    def action_edit(self):
        with suspend_app(self.app):
            self.text = edit_file(contents=self.text)
        self._update_editor()

    def _update_editor(self):
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

    def compose(self) -> ComposeResult:
        yield Button("New procedure", id="to_new_procedure")
        yield Button("Snapshot Before new procedure", id="to_snapshot_new_procedure")
        yield Footer()

    @on(Button.Pressed, "#to_new_procedure")
    def to_new_procedure(self):
        self.push_screen(NewProcedure(snapshot=False))

    @on(Button.Pressed, "#to_snapshot_new_procedure")
    def to_snapshot_new_procedure(self):
        self.push_screen(NewProcedure(snapshot=True))

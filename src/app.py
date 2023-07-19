import os
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import Popen
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
    Static,
)
from textual.widgets.option_list import Option

from .browser import BrowserWrapper


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
    browser: BrowserWrapper | None = None

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        /,
        snapshot=False,
    ) -> None:
        self.to_snapshot = snapshot
        self.snapshots = dict[str, Snapshot]()
        super().__init__(name, id, classes)

    def on_mount(self):
        if self.to_snapshot:
            self.app.push_screen(SnapshotNewProcedure(), self.receive_snapshots)

    def receive_snapshots(self, snapshots: list[Snapshot]):
        self.snapshots = {snap.time.isoformat(): snap for snap in snapshots}
        for id, snap in self.snapshots.items():
            self.snapshot_list.add_option(Option(snap.url, id=id))
            # TODO: File permissions so random things cannot access it.
            path = TMP_DIRECTORY / f"{id}.html"
            path.write_text(snap.html_content)

    def compose(self) -> ComposeResult:
        yield CollapsibleEditor(DEFAULT_PROCEDURE_SNIPPET, "python", label="Show code")
        self.snapshot_list = OptionList(id="snapshot_list")
        yield self.snapshot_list

    @on(OptionList.OptionSelected, "#snapshot_list")
    def snapshot_list_selected(self, *args):
        # TODO: How to actually tell which option is selected
        print(args)


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
            self.text = edit_file("state_dl.tmp.py", self.text)
        self._update_editor()

    def _update_editor(self):
        self.editor.update(Syntax(self.text, lexer=self.lexer))


TMP_DIRECTORY = Path("/tmp")


def edit_file(file_name, initial_contents: str) -> str:
    tmp_file = TMP_DIRECTORY / file_name
    tmp_file.write_text(initial_contents)
    editor = os.environ["VISUAL"] or os.environ["EDITOR"]
    proc = Popen([editor, tmp_file])
    proc.wait()
    return tmp_file.read_text()


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

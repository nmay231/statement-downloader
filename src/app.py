import os
import shlex
import sys
import time
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
    Static,
)

from .browser import Browser


@dataclass
class Snapshot:
    url: str
    html_content: str
    time: datetime


class SnapshotNewProcedure(Screen[list[Snapshot]]):
    snapshots: list[Snapshot]

    def compose(self) -> ComposeResult:
        self.snapshots = []
        with ContentSwitcher(initial="start") as switch:
            self.switch = switch
            with Container(id="start"):
                yield Static("Press <Enter> to launch browser")
                yield Input(placeholder="Initial URL", id="url_input")
            with Container(id="snapshots"):
                self.new_snapshot_button = Button("Take Snapshot", id="new_snapshot")
                yield self.new_snapshot_button
                self.snapshot_list = Container(id="snapshot_list")
                yield self.snapshot_list
                yield Button("Stop", id="stop_snapshot")

    @on(Button.Pressed, "#new_snapshot")
    async def new_snapshot(self):
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
        self.dismiss(self.snapshots)
        self.app.pop_screen()

    @on(Input.Submitted, "#url_input")
    async def start_snapshots(self):
        url = self.query_one("#url_input", Input).value
        self.switch.current = "snapshots"
        self.new_snapshot_button.focus()
        self.browser = Browser()
        await self.browser.start(url)

    async def on_unmount(self):
        await self.browser.cleanup()


@dataclass
class TODOProcedure:
    ...


class NewProcedure(Screen[TODOProcedure]):
    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        /,
        snapshot=False,
    ) -> None:
        self.snapshot = snapshot
        super().__init__(name, id, classes)

    def on_mount(self):
        if self.snapshot:
            self.app.push_screen(SnapshotNewProcedure())

    def compose(self) -> ComposeResult:
        yield Static(f"New procedure! {self.snapshot}")


class CollapsibleEditor(Static, can_focus=True):
    BINDINGS = [Binding("space", "toggle", "Toggle code preview")]
    DEFAULT_CSS = """
    CollapsibleEditor {
        background: $panel;
        color: $text;
        text-style: bold;
    }

    CollapsibleEditor:focus {
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

    show_toggle = reactive(False)

    def __init__(
        self,
        text: str,
        lexer: str,
        *,
        label: TextType,
        show_toggle: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.text = text
        self.label = label
        self.lexer = lexer
        self.show_toggle = show_toggle
        if show_toggle:
            self.add_class("open")

    def action_toggle(self):
        print("TOGGLE", self.show_toggle)
        self.show_toggle = not self.show_toggle
        self.update_toggle()
        if self.show_toggle:
            self.add_class("open")
        else:
            self.remove_class("open")

    def on_focus(self):
        print("FOCUSED!")

    def update_toggle(self):
        caret = "v" if self.show_toggle else ">"
        self.caret.update(Text.assemble(self.label, " ", caret))

    def compose(self) -> ComposeResult:
        self.caret = Static()
        self.update_toggle()
        yield self.caret
        yield Static(Syntax(self.text, lexer=self.lexer), id="editor")


class EditorShowcase(Screen):
    def compose(self) -> ComposeResult:
        yield Button("testing focus", id="button1")
        yield CollapsibleEditor(
            "print('hello world!')",
            "python",
            label="Editor demo",
            show_toggle=True,
            id="asdf",
        )
        yield Footer()

    def on_mount(self):
        self.query_one("#asdf").focus()


class MyApp(App):
    TITLE = "Browser Task Automaton"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        ("s", "suspend", "Suspend and print a message"),
    ]

    def compose(self) -> ComposeResult:
        yield Button("New procedure", id="to_new_procedure")
        yield Button("Snapshot Before new procedure", id="to_snapshot_new_procedure")
        yield Footer()

    def on_mount(self):
        self.push_screen(EditorShowcase())

    @on(Button.Pressed, "#to_new_procedure")
    def to_new_procedure(self):
        self.push_screen(NewProcedure(snapshot=False))

    @on(Button.Pressed, "#to_snapshot_new_procedure")
    def to_snapshot_new_procedure(self):
        self.push_screen(NewProcedure(snapshot=True))

    # Details: https://github.com/Textualize/textual/issues/1093
    # https://github.com/Textualize/textual/pull/1150
    def action_suspend(self) -> None:
        with self.suspend():
            tmp_file = Path("/tmp/_state_dl.tmp.py")
            tmp_file.touch()
            tmp_file.write_text("print('Hello world!')")
            editor = os.environ["VISUAL"] or os.environ["EDITOR"]
            proc = Popen(shlex.split(f"{editor} {tmp_file}"))
            proc.wait()
            print(tmp_file.read_text())
            time.sleep(2)

    @contextmanager
    def suspend(self) -> Iterator[None]:
        driver = self._driver

        if driver is not None:
            driver.stop_application_mode()
            with redirect_stdout(sys.stdout), redirect_stderr(sys.stderr):
                yield
            driver.start_application_mode()

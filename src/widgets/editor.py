import os
import tempfile
from subprocess import call as sh_run

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.widgets import (
    Static,
)

from ..utils import suspend_app


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

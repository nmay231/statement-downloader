import shlex
from pathlib import Path
from subprocess import Popen

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.timer import Timer
from textual.widgets import Static

from ..env import Context
from ..utils import suspend_app


class Editor(ScrollableContainer, can_focus=True):
    BINDINGS = [
        Binding("enter", "edit", "Edit text"),
    ]

    def __init__(
        self,
        ctx: Context,
        file_path: Path,
        *,
        default_contents: str,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        self.ctx = ctx
        self.file_path = file_path
        if not file_path.exists():
            file_path.write_text(default_contents)

    def compose(self) -> ComposeResult:
        self.scroll_view = Static(id="editor")
        self._update_scroll_view()
        yield self.scroll_view
        yield Static("<EOF>", id="eof")

    def on_click(self):
        self.action_edit()

    _editor_process: Popen | None = None
    _editor_timer: Timer | None = None

    def action_edit(self):
        if self._editor_process or self._editor_timer:
            return

        def _open():
            file = str(self.file_path).replace('"', '\\"')
            return Popen(shlex.split(self.ctx.edit_file.format(file=file)))

        if self.ctx.editor_in_terminal:
            with suspend_app(self.app):
                _open().wait()
            self._update_scroll_view()
        else:
            self.scroll_view.update("File is open in external editor")
            self._editor_process = _open()
            self._editor_timer = self.set_interval(3, self._poll_external_editor)

    def _poll_external_editor(self):
        assert self._editor_process and self._editor_timer
        if self._editor_process.poll() is None:
            return  # Editor is still running

        self._update_scroll_view()
        self._editor_timer.stop()
        self._editor_process = self._editor_timer = None

    def _update_scroll_view(self):
        # Performance be damned
        self.text = self.file_path.read_text()
        self.scroll_view.styles.height = 1 + self.text.count("\n")
        self.scroll_view.update(Syntax(self.text, lexer="python"))

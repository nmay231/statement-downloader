from textual import on
from textual.app import ComposeResult
from textual.containers import Center
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Static


class ConfirmDialog(ModalScreen[bool]):
    def __init__(
        self,
        message: str,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.message = message
        super().__init__(name, id, classes)

    def compose(self) -> ComposeResult:
        with Widget():
            yield Static(self.message)
            with Center(classes="button-row"):
                yield Button("Okay", id="okay")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#cancel", Button).focus()

    @on(Button.Pressed, "#okay")
    def okay(self):
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self.dismiss(False)

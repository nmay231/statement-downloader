import re

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Input

from ..env import Context, ProcedureInfo, Snapshot


class NewProcedure(Screen[ProcedureInfo]):
    def __init__(
        self,
        ctx: Context,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.ctx = ctx
        super().__init__(name, id, classes)

    def compose(self) -> ComposeResult:
        self.name_input = Input(placeholder="Procedure Name")
        yield self.name_input
        self.url_input = Input(placeholder="Starting URL")
        yield self.url_input
        with Widget(classes="button-row"):
            self.start_button = Button("Start", id="start")
            yield self.start_button
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel":
            self.dismiss()
        self.try_submit()

    common_url = re.compile("^(http|https|file)://")

    @on(Input.Submitted)
    def try_submit(self):
        name = self.name_input.value
        url = self.url_input.value
        if not name or not url:
            self.notify("Name and URL required")
            return
        if not self.common_url.match(url):
            url = f"https://{url}"

        self.dismiss(ProcedureInfo(name=name, snapshots=[Snapshot(uri=url)]))

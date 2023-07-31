from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Input

from .edit_procedure import EditProcedure

if TYPE_CHECKING:
    from ..app import MyApp


@dataclass
class PartialProcedure:
    name: str


class NewProcedure(Screen):
    def compose(self) -> ComposeResult:
        self.name_input = Input(placeholder="Procedure Name")
        yield self.name_input
        with Widget(classes="button-row"):
            self.start_button = Button("Start", id="start")
            yield self.start_button
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        self.app.pop_screen()
        if event.button.id == "start":
            # TODO: I should invert this control and have the edit procedure manage plumbing
            self.app.push_screen(
                EditProcedure(proc_name=self.name_input.value),
                cast("MyApp", self.app).save_procedure,
            )

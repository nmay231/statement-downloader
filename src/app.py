from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.driver import Driver
from textual.widget import Widget
from textual.widgets import Button, Footer, OptionList
from textual.widgets.option_list import Option

from .env import Config, Context, ProcedureInfo
from .screens.edit_procedure import EditProcedure
from .screens.new_procedure import NewProcedure
from .widgets.confirm_dialog import ConfirmDialog


class MyApp(App):
    TITLE = "Browser Task Automaton"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
    ]
    CSS_PATH = ["app.tcss"]

    def __init__(
        self,
        driver_class: type[Driver] | None = None,
        css_path=None,
        watch_css: bool = False,
    ):
        self._config = Config.load_from_path(Context.config_p)
        self.ctx = Context(self._config)
        super().__init__(driver_class, css_path, watch_css)

    def compose(self) -> ComposeResult:
        with Widget(classes="button-row"):
            yield Button("New procedure", id="to_new_procedure")
            yield Button(
                "Snapshot before new procedure",
                id="to_snapshot_new_procedure",
            )
            self.edit_procedure_button = Button(
                "Edit procedure",
                id="edit_procedure",
                disabled=True,
            )
            yield self.edit_procedure_button
            self.delete_procedure_button = Button(
                "Delete procedure", id="delete_procedure", disabled=True
            )
            yield self.delete_procedure_button
        self.procedure_list = OptionList(id="procedure_list")
        yield self.procedure_list
        yield Footer()  # TODO: Footer needs to be on all relevant screens

        for name, procedure in self.ctx.all_procedures.items():
            label = f"{name} <File missing>" if not procedure.exists else name
            self.procedure_list.add_option(Option(label, id=name))

    @on(Button.Pressed, "#to_new_procedure")
    def to_new_procedure(self):
        self.push_screen(NewProcedure(self.ctx))

    @on(Button.Pressed, "#to_snapshot_new_procedure")
    def to_snapshot_new_procedure(self):
        # TODO
        # self.push_screen(EditProcedure(snapshot=True))
        ...

    @on(OptionList.OptionHighlighted, "#procedure_list")
    async def snapshot_list_highlighted(self, selected: OptionList.OptionHighlighted) -> None:
        assert selected.option_id, "Should never be None"
        assert selected.option_id in self.ctx.all_procedures, "all_procedures out of date"
        proc = self.ctx.all_procedures[selected.option_id]

        label = "Recreate procedure" if not proc.exists else "Edit procedure"
        self.edit_procedure_button.disabled = False
        self.edit_procedure_button.label = label
        self.edit_procedure_button.refresh(layout=True)

        label = "Untrack procedure" if not proc.exists else "Delete procedure"
        self.delete_procedure_button.disabled = False
        self.delete_procedure_button.label = label
        self.delete_procedure_button.refresh(layout=True)

    @property
    def _selected_procedure(self) -> ProcedureInfo | None:
        index = self.procedure_list.highlighted
        if index is None:
            return None
        id = self.procedure_list.get_option_at_index(index).id
        return None if id is None else self.ctx.all_procedures.get(id)

    @on(Button.Pressed, "#edit_procedure")
    async def edit_procedure(self) -> None:
        proc = self._selected_procedure
        assert proc, "no procedure selected or it is missing"
        self.app.push_screen(
            EditProcedure(self.ctx, proc_name=proc.name),
            self.save_procedure,
        )

    @on(Button.Pressed, "#delete_procedure")
    def start_delete(self):
        proc = self._selected_procedure
        assert proc, "no procedure selected or it is missing"
        message = "Are you sure you want to [b]permanently[/] delete this?"
        self.app.push_screen(ConfirmDialog(message), self._delete_procedure)

    def _delete_procedure(self, delete: bool):
        if not delete:
            return
        proc = self._selected_procedure
        index = self.procedure_list.highlighted
        assert proc is not None and index is not None
        self.procedure_list.remove_option_at_index(index)  # UI
        self.ctx.all_procedures.pop(proc.name, None)  # Internal runtime
        self._config.procedures.pop(proc.name, None)  # Config
        self._config.save_to_path(self.ctx.config_p)
        # TODO: Move to /tmp, just in case?
        (self.ctx.procedures_dir_p / f"{proc.name}.py").unlink(missing_ok=True)  # Filesystem

    def save_procedure(self, proc: ProcedureInfo):
        if proc.name in self.ctx.all_procedures:
            return

        name = proc.name
        self.procedure_list.add_option(Option(name, id=name))  # UI
        self.ctx.all_procedures[name] = proc  # Internal runtime
        self._config.procedures[name] = proc  # Config
        self._config.save_to_path(self.ctx.config_p)

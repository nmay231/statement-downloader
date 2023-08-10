from textual import on
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.binding import Binding
from textual.widgets import Button, Footer, OptionList
from textual.widgets.option_list import Option

from .env import CONFIG_PATH, PROCEDURES_DIR, ProcedureInfo, config
from .screens.edit_procedure import EditProcedure
from .screens.new_procedure import NewProcedure


class MyApp(App):
    TITLE = "Browser Task Automaton"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
    ]
    CSS_PATH = ["app.tcss"]

    procedures = dict[str, ProcedureInfo | None]()

    def compose(self) -> ComposeResult:
        with Widget(classes="button-row"):
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
        self.push_screen(NewProcedure())

    @on(Button.Pressed, "#to_snapshot_new_procedure")
    def to_snapshot_new_procedure(self):
        # TODO
        # self.push_screen(EditProcedure(snapshot=True))
        ...

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
        self.app.push_screen(EditProcedure(proc_name=name), self.save_procedure)

    async def save_procedure(self, proc: ProcedureInfo):
        # TODO: Do I need manage display_name and file name separately?
        if proc.display_name in self.procedures:
            return

        name = proc.display_name
        self.procedure_list.add_option(Option(name, id=name))
        self.procedures[name] = proc
        config.procedures[name] = proc
        CONFIG_PATH.write_text(config.model_dump_json(indent=4))

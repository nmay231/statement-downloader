import json
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Static,
)


@dataclass
class Procedure:
    name: str


class SnapshotNewProcedure(Screen):
    def compose(self) -> ComposeResult:
        yield Button("Pop screen", id="pop")
        yield Button("To new procedure", id="to_new_procedure")

    @on(Button.Pressed, "#pop")
    def pop(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#to_new_procedure")
    def to_new_procedure(self):
        self.app.pop_screen()
        self.app.push_screen(NewProcedure())


class NewProcedure(Screen):
    def compose(self) -> ComposeResult:
        yield Static("New procedure! (press ctrl+q to quit)")


class SubScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("hello there")
        yield Button("Back to main menu", id="to_main_menu")

    @on(Button.Pressed, "#to_main_menu")
    def to_main_menu(self):
        self.app.pop_screen()


class MyApp(App):
    TITLE = "Browser Task Automaton"
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Button("New procedure", id="to_new_procedure")
        yield Button("Snapshot Before new procedure", id="to_snapshot_new_procedure")
        yield Footer()

    @on(Button.Pressed, "#to_sub_screen")
    def put_on_some_sub_screen(self):
        self.push_screen(SubScreen())

    @on(Button.Pressed, "#to_new_procedure")
    def to_new_procedure(self):
        self.push_screen(NewProcedure())

    @on(Button.Pressed, "#to_snapshot_new_procedure")
    def to_snapshot_new_procedure(self):
        self.push_screen(SnapshotNewProcedure())


def main():
    MyApp().run()


def main_old():
    config = json.loads(Path("./tmp_config.json").read_text())["options"][0]
    print(config)
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    auth_path = (Path.home() / ".local/share/state_dl/browser_context.json").resolve()
    context = browser.new_context(storage_state=auth_path if auth_path.exists() else None)

    page = context.new_page()
    page.goto(config["website"])
    table = page.locator("table")
    print(table)

    auth_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=auth_path)
    # page.wait_for_timeout(1000)
    context.close()


if __name__ == "__main__":
    main()

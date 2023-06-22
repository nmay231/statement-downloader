from pathlib import Path

from playwright.sync_api import sync_playwright
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import (
    Footer,
    Header,
    ListItem,
    ListView,
    Markdown,
    OptionList,
    Static,
    _option_list,
)
from textual.widgets.option_list import Option


class MyApp(App):
    TITLE = "Browser Task Automaton"

    def compose(self) -> ComposeResult:
        with Container(id="HomeScreen"):
            yield Header(show_clock=True)
            yield Static("asdfasdf asdf asdf")
            self.list = OptionList(
                Option("test1", id="test1"),
                Option("test2", id="test2"),
                Option("test3", id="test3"),
            )
            yield self.list

    @on(OptionList.OptionSelected)
    def print_value(self, event: OptionList.OptionSelected) -> None:
        print(
            "EVENT!",
            self.list == event.option_list,
            self.list.get_option_at_index(event.option_index).id,
        )


def main():
    MyApp().run()


def main_old():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    auth_path = (Path.home() / ".local/share/state_dl/browser_context.json").resolve()
    context = browser.new_context(storage_state=auth_path if auth_path.exists() else None)

    page = context.new_page()

    page.goto("https://github.com/")
    input()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=auth_path)
    # page.wait_for_timeout(1000)
    context.close()


if __name__ == "__main__":
    main()

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    Footer,
    Input,
    Label,
    ListView,
    OptionList,
    Static,
)


class Browser:
    # TODO: Context manager? It's easy enough to do, but I don't know if I can
    #       synchronize a context manager to the lifecycle of a textual component
    async def start(self, url: str):
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        self._auth_path = (
            Path.home() / ".local/share/state_dl/browser_context.json"
        ).resolve()
        p = self._auth_path
        self.context = await browser.new_context(storage_state=p if p.exists() else None)

        self.page = await self.context.new_page()
        await self.page.goto(url)

    async def cleanup(self):
        self._auth_path.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=self._auth_path)
        await self.context.close()


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


class MyApp(App):
    TITLE = "Browser Task Automaton"
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Button("New procedure", id="to_new_procedure")
        yield Button("Snapshot Before new procedure", id="to_snapshot_new_procedure")
        yield Footer()

    @on(Button.Pressed, "#to_new_procedure")
    def to_new_procedure(self):
        self.push_screen(NewProcedure(snapshot=False))

    @on(Button.Pressed, "#to_snapshot_new_procedure")
    def to_snapshot_new_procedure(self):
        self.push_screen(NewProcedure(snapshot=True))


def main():
    MyApp().run()


if __name__ == "__main__":
    main()

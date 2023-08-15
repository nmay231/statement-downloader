from dataclasses import dataclass
from datetime import datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button,
    ContentSwitcher,
    Input,
    Static,
)

from ..browser import BrowserWrapper
from ..env import Context


@dataclass
class Snapshot:
    url: str
    html_content: str
    time: datetime


class SnapshotNewProcedure(Screen[list[Snapshot]]):
    snapshots: list[Snapshot]
    browser: BrowserWrapper | None = None

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
        self.snapshots = []
        with ContentSwitcher(initial="start") as self.switch:
            with Container(id="start"):
                yield Static("Press <Enter> to launch browser")
                yield Input(placeholder="Initial URL", id="url_input")
            with Container(id="snapshots"):
                yield Button("Take Snapshot", id="new_snapshot")
                self.snapshot_list = Container(id="snapshot_list")
                yield self.snapshot_list
                yield Button("Stop", id="stop_snapshot")

    @on(Button.Pressed, "#new_snapshot")
    async def new_snapshot(self):
        assert self.browser, "forgot to init browser"
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
        self.dismiss(result=self.snapshots)

    @on(Input.Submitted, "#url_input")
    async def start_snapshots(self):
        url = self.query_one("#url_input", Input).value
        self.switch.current = "snapshots"
        self.query_one("#new_snapshot", Button).focus()
        self.browser = BrowserWrapper()
        await self.browser.start(self.ctx, url)
        await self.new_snapshot()  # The user most likely wants to keep the first page

    async def on_unmount(self):
        if self.browser:
            await self.browser.cleanup()

import importlib
import sys
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual import on, work
from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, OptionList, SelectionList, Static
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from ..browser import BrowserWrapper
from ..env import Context, ProcedureInfo, Snapshot
from ..widgets.editor import Editor


class EditProcedure(Screen[ProcedureInfo]):
    _entries: dict[str, Any] = {}

    def __init__(
        self,
        ctx: Context,
        proc: ProcedureInfo,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name, id, classes)
        self.proc = deepcopy(proc)
        self.ctx = ctx
        # TODO: More robust yet still consistent filename
        self.snapshot_dir = Path(f"/tmp/state_dl/{proc.name}")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        if not self.procedure_file.exists():
            self.procedure_file.write_text(
                self.ctx.default_procedure_snippet.format(initial_url=self.initial_url)
            )

    @property
    def procedure_file(self):
        return self.ctx.procedures_dir_p / f"{self.proc.name}.py"

    @property
    def initial_url(self):
        return self.proc.snapshots[0].uri if self.proc.snapshots else "https://example.com"

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="editor"):
            self.editor = Editor(
                self.ctx,
                self.procedure_file,
                default_contents=self.ctx.default_procedure_snippet,
            )
            yield self.editor
        with ScrollableContainer(id="misc"):
            self.snapshot_list = OptionList(id="snapshot_list")
            self.snapshot_list.border_title = "URL Snapshots"
            yield self.snapshot_list
            with Widget(classes="button-row"):
                yield Button("Run `find()`", id="find")
                yield Button("Run `process()`", id="process")
                yield Static(classes="button-row-spacing")
                yield Button("Live snapshot", id="snapshot-live")
                yield Button("Static snapshot", id="snapshot-static")
                yield Static(classes="button-row-spacing")
                yield Button("Save procedure", id="save")
            self.name_label = Static(self.procedure_file.stem)
            yield self.name_label
            self.options = SelectionList[str]()
            self.options.border_title = "Entries"
            yield self.options
        with ScrollableContainer(id="debug_output") as container:
            container.border_title = "Debug Output (stdout/stderr)"
            self.output = Static()
            yield self.output

    def on_mount(self) -> None:
        for snap in self.proc.snapshots:
            self.snapshot_list.add_option(Option(f"[i]{snap.time}[/] [b]{snap.uri}[/]"))

    @on(OptionList.OptionSelected, "#snapshot_list")
    async def snapshot_list_selected(self, selected: OptionList.OptionSelected) -> None:
        self.snapshot_list.disabled = True
        self._browser_goto(self.proc.snapshots[selected.option_index].uri)

    @work
    async def _browser_goto(self, uri: str):
        """
        Wrapped in a worker since launching a browser the
        first time can exceed a message-handler timeout
        """
        await self.get_browser(uri)
        self.snapshot_list.disabled = False

    # TODO: Move browser to .env.Context()
    _browser: BrowserWrapper | None = None

    async def get_browser(self, url: str | None = None) -> BrowserWrapper:
        if self._browser is not None:
            if url:
                await self._browser.page.goto(url)
            return self._browser
        # TODO: Have run_find() and run_process() call proc_module.init() to goto(initial_url)
        self._browser = await BrowserWrapper.init(
            ctx=self.ctx,
            initial_url=url or self.initial_url,
            on_close=self._clear_browser,
        )
        return self._browser

    async def _clear_browser(self):
        assert self._browser
        self._browser = None

    @contextmanager
    def _import_procedure(self):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            # TODO: Timeout to catch infinite loops
            module_name = self.procedure_file.stem
            package = self.ctx.procedures_dir_p.stem
            module = sys.modules.get(module_name)

            imported = False
            try:
                if not module:
                    module = importlib.import_module(name=module_name, package=package)
                else:
                    module = importlib.reload(module)
                imported = True
                yield module
            except Exception:
                traceback.print_exc()
                if not imported:
                    yield None

        output.seek(0)
        self.output.update(escape(output.read()))

    @contextmanager
    def _set_status(self, status: str, end_status: str | None = None):
        self.name_label.update(f"{self.procedure_file.stem} <{status}>")
        yield
        # TODO: How to restore to the previous name_label.content?
        if not end_status:
            self.name_label.update(self.procedure_file.stem)
        else:
            self.name_label.update(f"{self.procedure_file.stem} <{end_status}>")

    @on(Button.Pressed, "#find")
    async def run_find(self):
        self._run_find()

    @work
    async def _run_find(self):
        with self._import_procedure() as module, self._set_status("PENDING"):
            if not module:
                return
            wrapper = await self.get_browser()

            self.options.clear_options()
            entries = await module.find(wrapper.page)
            assert isinstance(entries, list), "expected `find()` to return list[Entry]"
            self._entries = {e.id: e for e in entries}
            self.options.add_options(
                [
                    Selection(
                        entry.label,
                        entry.id,
                        initial_state=not index,
                    )
                    for index, entry in enumerate(entries)
                ]
            )

    @on(Button.Pressed, "#process")
    async def run_process(self):
        self._run_process()

    @work
    async def _run_process(self):
        if not self._entries:
            self.output.update("Run [bold]find()[/] first, and ensure something's returned")
            return

        with self._import_procedure() as module, self._set_status("PENDING", "FINISHED"):
            if not module:
                return
            wrapper = await self.get_browser()

            entries = [self._entries[id] for id in self.options.selected]
            await module.process(wrapper.page, entries)

    @on(Button.Pressed, "#save")
    async def save_procedure(self):
        if self._browser:
            await self._browser.context.close()
            assert self._browser is None, "self._clear_browser callback should have run"
        self.dismiss(self.proc)

    @on(Button.Pressed, "#snapshot-live")
    async def live_snapshot(self):
        browser = await self.get_browser()
        snap = Snapshot(uri=browser.page.url)
        self.proc.snapshots.append(snap)
        self.snapshot_list.add_option(Option(f"[i]{snap.time}[/] [b]{snap.uri}[/]"))

    @on(Button.Pressed, "#snapshot-static")
    async def snapshot_static(self):
        browser = await self.get_browser()
        content = await browser.page.content()
        now = datetime.now()
        path = self.snapshot_dir / f"{now}.html"
        path.write_text(content)
        snap = Snapshot(uri=f"file://{path}", time=now)
        self.proc.snapshots.append(snap)
        self.snapshot_list.add_option(Option(f"[i]{snap.time}[/] [b]{snap.uri}[/]"))

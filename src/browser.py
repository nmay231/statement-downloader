from typing import TYPE_CHECKING, Awaitable, Callable

from playwright.async_api import BrowserContext, Page, async_playwright
from typing_extensions import Self

if TYPE_CHECKING:
    from .env import Context


class BrowserWrapper:
    def __init__(self, _external=True):
        if _external:
            raise RuntimeError(f"Use {self.__class__.__name__}.init()")

    @classmethod
    async def init(
        cls, *, ctx: "Context", initial_url: str | None, on_close: Callable | None = None
    ) -> Self:
        self = cls(_external=False)
        self._user_on_close = on_close
        await self._start(ctx, initial_url)
        return self

    async def _start(self, ctx: "Context", url: str | None) -> None:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False, timeout=15000)

        # TODO: Use contexts listed in ctx
        self._auth_path = ctx.home_p / "browser_context.json"
        ss = self._auth_path if self._auth_path.exists() else None
        self.context = await browser.new_context(storage_state=ss)
        if not ss:
            await self.context.storage_state(path=self._auth_path)

        self.context.on("close", self._on_close)
        self.context.on("page", self._increment_page_count)

        self.page = await self.context.new_page()
        if url:
            await self.page.goto(url)

    _page_count = 0

    def _increment_page_count(self, page: Page):
        self._page_count += 1
        page.on("close", self._decrement_page_count)

    async def _decrement_page_count(self, _page: Page):
        self._page_count -= 1
        if self._page_count <= 0:
            await self.context.storage_state(path=self._auth_path)
            await self.context.close()

    _user_on_close: Callable[[], None | Awaitable[None]] | None

    async def _on_close(self, _browser: BrowserContext):
        if self._user_on_close:
            result = self._user_on_close()
            if isinstance(result, Awaitable):
                await result

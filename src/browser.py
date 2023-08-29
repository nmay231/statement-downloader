from typing import TYPE_CHECKING

from playwright.async_api import async_playwright
from typing_extensions import Self

if TYPE_CHECKING:
    from .env import Context


class BrowserWrapper:
    def __init__(self, external=True):
        if external:
            raise RuntimeError(f"Use {self.__class__.__name__}.init()")

    @classmethod
    async def init(cls, *, ctx: "Context", initial_url: str | None) -> Self:
        self = cls(external=False)
        await self._start(ctx, initial_url)
        return self

    async def _start(self, ctx: "Context", url: str | None):
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        self._auth_path = ctx.home_p / "browser_context.json"
        p = self._auth_path
        self.context = await browser.new_context(storage_state=p if p.exists() else None)

        self.page = await self.context.new_page()
        if url:
            await self.page.goto(url)

    async def cleanup(self):
        self._auth_path.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=self._auth_path)
        await self.context.close()

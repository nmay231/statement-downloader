from typing import TYPE_CHECKING

from playwright.async_api import async_playwright

if TYPE_CHECKING:
    from .env import Context


class BrowserWrapper:
    # TODO: Context manager? It's easy enough to do, but I don't know if I can
    #       synchronize a context manager to the lifecycle of a textual component
    async def start(self, ctx: "Context", url: str | None):
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        # TODO: This should use context since it will eventually allow multiple browser contexts
        self._auth_path = ctx.home_p / "browser_context.json"
        p = self._auth_path
        self.context = await browser.new_context(storage_state=p if p.exists() else None)

        self.page = await self.context.new_page()
        # if url:
        # TODO: allow new procedure to take a default url
        if url or True:
            await self.page.goto(
                "https://en.wikipedia.org/wiki/Portraits_of_presidents_of_the_United_States"
            )

    async def cleanup(self):
        self._auth_path.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=self._auth_path)
        await self.context.close()

from playwright.async_api import async_playwright

from .env import CONFIG_PATH


class BrowserWrapper:
    # TODO: Context manager? It's easy enough to do, but I don't know if I can
    #       synchronize a context manager to the lifecycle of a textual component
    async def start(self, url: str):
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        self._auth_path = CONFIG_PATH / "browser_context.json"
        p = self._auth_path
        self.context = await browser.new_context(storage_state=p if p.exists() else None)

        self.page = await self.context.new_page()
        await self.page.goto(url)

    async def cleanup(self):
        self._auth_path.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=self._auth_path)
        await self.context.close()

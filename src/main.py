from pathlib import Path

from playwright.sync_api import sync_playwright

playwright = sync_playwright().start()


def main():
    browser = playwright.chromium.launch(headless=False)
    auth_context_path = (
        Path.home() / ".local/share/state_dl/browser_context.json"
    ).resolve()
    context = browser.new_context(storage_state=auth_context_path)

    page = context.new_page()

    page.goto("https://github.com/")
    input()
    context.storage_state(path=auth_context_path)
    # page.wait_for_timeout(1000)
    context.close()

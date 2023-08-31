from dataclasses import dataclass

from playwright.async_api import Page


@dataclass
class Entry:
    # Required
    id: str
    label: str
    # You can add more fields if desired


async def find(page: Page) -> list[Entry]:
    """Return a list of entries that will be presented in a feed"""
    # TODO: Put this into an explicit init() function
    # await page.goto("{initial_url}")
    print("finding in page...")
    return [Entry("id_text", "Displayed label")]


async def process(page: Page, entries: list[Entry]) -> None:
    """Given a (filtered) list of entries, process them however you wish"""
    print("processing...")

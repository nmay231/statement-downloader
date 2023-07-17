from dataclasses import dataclass

from playwright.async_api import Browser, Page

# TODO: Configuration will eventually be done using an object imported from state_dl for type safety
PROCEDURE_NAME = "your procedure"


@dataclass
class Entry:
    # Required
    id: str
    label: str
    # User defined
    # ...


async def find(browser: Browser, page: Page) -> list[Entry]:
    return []


async def process(browser: Browser, page: Page, picked: list[Entry]) -> None:
    pass

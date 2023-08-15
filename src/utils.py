import sys
from contextlib import (
    contextmanager,
    redirect_stderr,
    redirect_stdout,
)
from typing import Iterator

from textual.app import App


# Details: https://github.com/Textualize/textual/issues/1093
# https://github.com/Textualize/textual/pull/1150
@contextmanager
def suspend_app(app: App) -> Iterator[None]:
    driver = app._driver

    if driver is not None:
        driver.stop_application_mode()
        with redirect_stdout(sys.stdout), redirect_stderr(sys.stderr):
            yield
            driver.start_application_mode()

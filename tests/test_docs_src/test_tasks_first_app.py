"""`docs_src/tasks/first_app.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox.testing import FakeDaemon


async def test_first_app(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType]
) -> None:
    app = load_example("tasks/first_app.py").app
    # Commands of the fake environment print their last argument.
    assert await app.run("uname") == "uname -sm"
    assert app.get_task("uname").description == "Says which system the sandbox runs."
    assert fake_environment.sandboxes == {}

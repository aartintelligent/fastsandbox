"""`docs_src/tasks/dependencies.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox.testing import FakeDaemon


async def test_dependencies(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType]
) -> None:
    app = load_example("tasks/dependencies.py").app
    # Commands of the fake environment print their last argument.
    assert await app.run("describe") == {
        "python": "--version",
        "scratch": "/tmp/scratch",
        "registry": "https://pypi.org/simple",
    }
    commands = [
        r.json()["cmd"] for r in fake_environment.requests_to("POST", "/sandbox/{name}/exec")
    ]
    assert commands[-1] == ["rm", "-rf", "/tmp/scratch"]

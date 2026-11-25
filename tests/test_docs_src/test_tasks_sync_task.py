"""`docs_src/tasks/sync_task.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox.testing import FakeDaemon


async def test_sync_task(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType]
) -> None:
    app = load_example("tasks/sync_task.py").app
    assert await app.run("disk_usage", path="/home") == "/home"
    assert await app.run("disk_usage") == "/"
    assert fake_environment.sandboxes == {}

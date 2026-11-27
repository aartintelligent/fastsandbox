"""The tests against the real daemon of the current user (`just test-live`).

Every test under this directory is marked `live`, which the default run
leaves out. They create throw-away sandboxes from the `shell` kit, forged
without the `sbx` CLI, and delete them; only dummy values are used.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import fastsandbox

HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if HERE in Path(item.path).parents:
            item.add_marker(pytest.mark.live)


@pytest.fixture
async def client() -> fastsandbox.Client:
    return await fastsandbox.connect()

"""`docs_src/testing/test_environment.py`, the fake environment of an unchanged application."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest


async def test_environment_example(
    load_example: Callable[[str], ModuleType], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await load_example("testing/test_environment.py").test_python_version(tmp_path, monkeypatch)

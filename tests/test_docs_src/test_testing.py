"""`docs_src/testing/test_word_count.py`, the example of testing an application."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


async def test_word_count_example(
    load_example: Callable[[str], ModuleType], tmp_path: Path
) -> None:
    await load_example("testing/test_word_count.py").test_word_count(tmp_path)

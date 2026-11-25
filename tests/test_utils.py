"""The shared helpers."""

from __future__ import annotations

import pytest

from fastsandbox.utils import parse_timeout


def test_durations() -> None:
    assert parse_timeout("10m") == 600
    assert parse_timeout("1h30m") == 5400
    assert parse_timeout("500ms") == 0.5
    assert parse_timeout(12) == 12.0
    with pytest.raises(ValueError, match="invalid duration"):
        parse_timeout("soon")

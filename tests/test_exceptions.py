"""Errors of the daemon as exceptions."""

from __future__ import annotations

from pathlib import Path

import pytest

import fastsandbox
from fastsandbox import (
    KitPackage,
    NotFoundError,
)
from fastsandbox.exceptions import KitPackageError


async def test_errors_carry_the_answer_of_the_daemon(client: fastsandbox.Client) -> None:
    with pytest.raises(NotFoundError) as raised:
        await client.sandboxes.get("nope")
    assert raised.value.status == 404
    assert raised.value.operation == "sandbox inspection"
    assert await client.sandboxes.find("nope") is None


def test_the_path_of_an_error_is_a_string(tmp_path: Path) -> None:
    with pytest.raises(KitPackageError) as raised:
        KitPackage.open(tmp_path / "missing")
    assert raised.value.path == str(tmp_path / "missing" / "create-body.json")

"""Errors of the daemon as exceptions."""

from __future__ import annotations

import pytest

import fastsandbox
from fastsandbox import (
    NotFoundError,
)


async def test_errors_carry_the_answer_of_the_daemon(client: fastsandbox.Client) -> None:
    with pytest.raises(NotFoundError) as raised:
        await client.sandboxes.get("nope")
    assert raised.value.status == 404
    assert raised.value.operation == "sandbox inspection"
    assert await client.sandboxes.find("nope") is None

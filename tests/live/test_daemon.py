"""The daemon of the current user."""

from __future__ import annotations

import fastsandbox


async def test_health(client: fastsandbox.Client) -> None:
    assert client.health.is_healthy
    low, high = fastsandbox.SUPPORTED_API
    assert low <= client.health.api_version < high

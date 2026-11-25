"""Network rules scoped to a sandbox."""

from __future__ import annotations

import fastsandbox
from fastsandbox.models import (
    RuleChange,
)
from fastsandbox.testing import FakeDaemon


async def test_network_rules_are_scoped(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    async with client.create("job-3", kit=package) as sandbox:
        result = await sandbox.allow_hosts("pypi.org")
        assert result.is_applied
        applied = await client.policy.apply_all(RuleChange.deny("example.org").for_sandbox("job-3"))
        assert applied[0].created[0].resource == "example.org"
    rules = await client.policy.rules()
    assert {(r.resources[0], r.sandbox_id) for r in rules.rules} == {
        ("pypi.org", "job-3"),
        ("example.org", "job-3"),
    }

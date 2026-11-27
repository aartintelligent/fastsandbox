"""Credentials and secrets."""

from __future__ import annotations

import fastsandbox
from fastsandbox.models import (
    CredentialsOutcome,
    CredentialsUpdate,
    CustomSecret,
    wire,
)
from fastsandbox.testing import FakeDaemon, Request, Response


def test_secrets_are_exposed_to_the_extension_only() -> None:
    secret = CustomSecret.new(["api.example.com"], "PLACEHOLDER", "dummy-value")
    assert "dummy-value" not in repr(secret)
    assert "dummy-value" not in secret.model_dump_json()
    assert wire(secret)["value"] == "dummy-value"
    assert wire(secret)["target"] == "api.example.com"


def test_sandbox_secrets_are_named_as_sbx_names_them() -> None:
    update = CredentialsUpdate().with_sandbox_secret("job-42", "github", "dummy")
    shape = wire(update)
    assert shape["credential_values"] == [{"service": "github", "value": "dummy"}]
    assert shape["credential_sources"] == {
        "github": {"source": "SANDBOX_STORED_CREDENTIAL_JOB_42_GITHUB", "type": "env"}
    }


async def test_credential_updates_report_the_services_the_daemon_withholds(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    @daemon.route("POST", "/sandbox/{name}/credentials")
    def withheld(request: Request) -> Response:
        return Response(200, {"message": "Credentials updated", "withheld": ["openai"]})

    sandbox = await client.create("job-1", kit=package)
    outcome = await sandbox.push_service_secret("openai", "dummy")
    assert outcome == CredentialsOutcome(message="Credentials updated", withheld=["openai"])
    assert (await sandbox.push_credentials(CredentialsUpdate())).withheld == ["openai"]
    assert (await sandbox.remove_service_secret("openai")).message == "Credentials updated"


async def test_credential_updates_withhold_nothing_by_default(
    client: fastsandbox.Client, package: fastsandbox.KitPackage
) -> None:
    sandbox = await client.create("job-1", kit=package)
    outcome = await sandbox.push_service_secret("github", "dummy")
    assert outcome.withheld == []
    assert outcome.credential_source_updates_applied is None


async def test_creation_reports_the_credentials_the_daemon_withholds(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    @daemon.route("POST", "/sandbox")
    def created(request: Request) -> Response:
        result = {"id": "1", "name": "job-1", "agent": "claude", "status": "running"}
        return Response(200, lines=[{"result": {**result, "withheld": ["anthropic"]}}])

    creation = client.create("job-1", kit=package)
    await creation
    assert creation.created is not None
    assert creation.created.withheld == ["anthropic"]

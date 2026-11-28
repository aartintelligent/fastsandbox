"""Creating sandboxes."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

import fastsandbox
from fastsandbox import (
    ConflictError,
)
from fastsandbox.testing import FakeDaemon, Request, Response


def held_creation(daemon: FakeDaemon, answer: Response | None = None) -> tuple[Any, Any]:
    """Holds the creations of `daemon` until released, then answers `answer`, or creates."""
    started, release = asyncio.Event(), asyncio.Event()

    @daemon.route("POST", "/sandbox")
    async def create(request: Request) -> Response:
        started.set()
        await release.wait()
        if answer is not None:
            return answer
        body = request.json()
        created = {
            "id": "sandbox-1",
            "name": body["name"],
            "agent": body["agent"],
            "status": "running",
            "workspace": "",
        }
        daemon.sandboxes[body["name"]] = {**created, "ports": [], "labels": {}, "request": body}
        return Response(200, lines=[{"result": created}])

    return started, release


async def test_create_awaited_keeps_the_sandbox(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    creation = client.create("job-1", kit=package, env={"MODE": "test"}, cpus=2)
    sandbox = await creation
    assert sandbox.name == "job-1"
    assert creation.created is not None
    assert creation.created.status == "running"
    request = daemon.sandboxes["job-1"]["request"]
    assert request["environment"] == {"MODE": "test"}
    assert request["cpus"] == 2
    assert [info.name for info in await client.sandboxes.list()] == ["job-1"]
    with pytest.raises(ConflictError):
        await client.create("job-1", kit=package)


async def test_create_as_context_deletes_the_sandbox(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    async with client.create(kit=package, workspace="/tmp") as sandbox:
        assert sandbox.name in daemon.sandboxes
        assert daemon.sandboxes[sandbox.name]["request"]["workspace"] == "/tmp"
    assert daemon.sandboxes == {}


@pytest.mark.parametrize("entered", [True, False], ids=["context", "awaited"])
async def test_a_cancelled_creation_deletes_the_sandbox_it_made(
    client: fastsandbox.Client,
    daemon: FakeDaemon,
    package: fastsandbox.KitPackage,
    entered: bool,
) -> None:
    started, release = held_creation(daemon)

    async def create() -> None:
        creation = client.create("cancelled", kit=package)
        if entered:
            async with creation:
                pass
        else:
            await creation

    creating = asyncio.create_task(create())
    await started.wait()
    creating.cancel()
    # The daemon creates the sandbox after the caller was cancelled.
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await creating
    assert daemon.sandboxes == {}
    assert len(daemon.requests_to("DELETE", "/sandbox/{name}")) == 1


async def test_a_cancelled_creation_leaves_the_sandbox_of_another(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    await client.create("taken", kit=package)
    started, release = held_creation(daemon, Response(409, {"message": "taken already exists"}))
    creating = asyncio.create_task(client.create("taken", kit=package).__aenter__())
    await started.wait()
    creating.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await creating
    assert "taken" in daemon.sandboxes
    assert daemon.requests_to("DELETE", "/sandbox/{name}") == []


async def test_a_creation_cancelled_twice_gives_up_waiting(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    started, release = held_creation(daemon)
    creating = asyncio.create_task(client.create("twice", kit=package).__aenter__())
    await started.wait()
    creating.cancel()
    # Once it waits for the creation to end, a second cancellation stops the wait.
    await asyncio.sleep(0)
    creating.cancel()
    with pytest.raises(asyncio.CancelledError):
        await creating
    release.set()
    assert daemon.requests_to("DELETE", "/sandbox/{name}") == []

"""Dependencies and the lifespan."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Annotated, Any

from fastsandbox import (
    Context,
    Depends,
    FastSandbox,
)
from fastsandbox.testing import FakeDaemon


async def test_dependencies_and_lifespan(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox]
) -> None:
    events: list[str] = []

    @contextlib.asynccontextmanager
    async def lifespan(app: FastSandbox) -> AsyncIterator[dict[str, Any]]:
        events.append("start")
        yield {"token": "dummy-token"}
        events.append("stop")

    def settings() -> dict[str, str]:
        return {"region": "eu"}

    async def token(ctx: Context) -> AsyncIterator[str]:
        events.append("open")
        yield str(ctx.state["token"])
        events.append("close")

    def counter() -> Iterator[int]:
        yield len(events)

    app = make_app(lifespan=lifespan)

    @app.task
    async def use(
        token: Annotated[str, Depends(token)],
        again: Annotated[str, Depends(token)],
        config: Annotated[dict[str, str], Depends(settings)],
        seen: Annotated[int, Depends(counter)],
    ) -> str:
        events.append("run")
        assert again == token
        return f"{token}:{config['region']}:{seen}"

    async with app:
        assert await app.run("use") == "dummy-token:eu:2"
        assert await use() == "dummy-token:eu:5"
    assert events == ["start", "open", "run", "close", "open", "run", "close", "stop"]

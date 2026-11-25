"""What a task run has access to."""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from typing import TYPE_CHECKING, Any, TypeVar

from .exceptions import TaskError
from .utils import as_coroutine

if TYPE_CHECKING:
    from collections.abc import Awaitable, Mapping

    from .agents import AgentRunner
    from .applications import FastSandbox
    from .client import Client
    from .sandbox import Sandbox
    from .tasks import Task
    from .types import ProgressHandler

T = TypeVar("T")

__all__ = ["Context"]


class Context:
    """What a task run has access to.

    It is injected into a task, or a dependency, by annotating a parameter with `Context`.

    Attributes:
        app: The application.
        task: The task being run.
        run_id: The identifier of this run.
        client: The client of the daemon.
        sandbox: The sandbox of the run.
        state: What the lifespan of the application yielded.
        logger: The logger of the task, `fastsandbox.task.<name>`.

    """

    def __init__(
        self,
        app: FastSandbox,
        task: Task,
        client: Client,
        sandbox: Sandbox,
        agent: AgentRunner | None,
        state: Mapping[str, Any],
        loop: asyncio.AbstractEventLoop,
        progress: ProgressHandler | None,
    ) -> None:
        self.app = app
        self.task = task
        self.run_id = uuid.uuid4().hex
        self.client = client
        self.sandbox = sandbox
        self.state = state
        self.logger = logging.getLogger(f"fastsandbox.task.{task.name}")
        self._agent = agent
        self._loop = loop
        self._progress = progress

    @property
    def agent(self) -> AgentRunner:
        """The agent of the sandbox, for a task declared with `app.agent`.

        Raises:
            TaskError: When the task has no agent.
        """
        if self._agent is None:
            raise TaskError(f"task {self.task.name} has no agent: declare it with app.agent")
        return self._agent

    def log(self, message: str, level: int = logging.INFO) -> None:
        """Logs `message` with the logger of the task."""
        self.logger.log(level, "%s [%s] %s", self.task.name, self.sandbox.name, message)

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        """Reports the progress of the run to the progress handler of the call."""
        self.logger.debug("progress %s/%s %s", progress, total, message or "")
        if self._progress is not None:
            outcome = self._progress(progress, total, message)
            if inspect.isawaitable(outcome):
                await outcome

    def wait(self, awaitable: Awaitable[T]) -> T:
        """Runs `awaitable` on the event loop from a synchronous task.

        Returns its result, e.g. `ctx.wait(ctx.sandbox.exec("ls"))`.
        """
        future = asyncio.run_coroutine_threadsafe(as_coroutine(awaitable), self._loop)
        return future.result()

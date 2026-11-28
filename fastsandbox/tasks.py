"""The tasks of an application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from pydantic import BaseModel, TypeAdapter

    from .agents import AgentProfile
    from .applications import FastSandbox
    from .dependencies.models import Parameter
    from .kits import Kit, KitPackage
    from .network import Network
    from .utils import PerLoop

__all__ = ["Task"]


@dataclass
class Task:
    """A task of an application: a function run in a throw-away sandbox.

    Call it (`await task(repo=".")`) to run it through its application.

    Attributes:
        app: The application of the task.
        name: The name of the task.
        fn: The function of the task.
        description: Its documentation, from the docstring by default.
        kit: The kit of its sandbox.
        network: The network rules of its sandbox.
        timeout: The deadline of a run, in seconds.
        env: Environment variables of its sandbox.
        cpus: Number of virtual CPUs of its sandbox.
        memory: Memory limit of its sandbox, e.g. `4g`.
        keep: Whether the sandbox is kept after the run, for debugging.
        agent: The agent of the task, for one declared with `app.agent`.
        allow_agent_hosts: Whether the hosts the agent needs are allowed
            along with `network`.
        input_model: The Pydantic model of the inputs.
        output: The validator of the result, from the return annotation.
    """

    app: FastSandbox
    name: str
    fn: Callable[..., Any]
    description: str
    kit: Kit | KitPackage | str
    network: Network
    timeout: float | None
    env: dict[str, str]
    cpus: int | None
    memory: str | None
    keep: bool
    agent: AgentProfile | None
    allow_agent_hosts: bool
    parameters: list[Parameter] = field(repr=False)
    input_model: type[BaseModel] = field(repr=False)
    output: TypeAdapter[Any] | None = field(repr=False)
    semaphore: PerLoop[asyncio.Semaphore] | None = field(default=None, repr=False)

    async def __call__(self, **arguments: Any) -> Any:
        """Runs the task through its application (see `FastSandbox.run`)."""
        return await self.app.run(self, **arguments)

    @property
    def input_schema(self) -> dict[str, Any]:
        """The JSON schema of the inputs."""
        return self.input_model.model_json_schema()

    @property
    def output_schema(self) -> dict[str, Any] | None:
        """The JSON schema of the result, when the task declares its type."""
        return self.output.json_schema() if self.output is not None else None

"""FastSandbox: a declarative framework for tasks that run in sandboxes.

An application declares tasks with decorators; each call of a task runs in a
throw-away sandbox, created from its kit, given its network rules and
credentials, kept running while the task runs, and deleted afterwards. The
signature of the task drives the rest: parameters
are validated by Pydantic from their type hints, a `Context` (or a `Sandbox`,
a `Client`, an `AgentRunner`) is injected by annotation, `Depends` resolves
dependencies, and `Annotated` markers mount or upload host directories.

Example:
    >>> app = FastSandbox("ci")
    >>>
    >>> @app.task(kit="shell", network=Network.allow("pypi.org"), timeout="10m")
    ... async def run_tests(ctx: Context, repo: Annotated[Path, Uploaded("/work")]) -> bool:
    ...     return (await ctx.sandbox.exec("cd /work && make test")).ok
    >>>
    >>> await app.run("run_tests", repo=".")
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import inspect
import io
import logging
import re
import sys
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_type_hints, overload

from pydantic import TypeAdapter

from .agents import AgentProfile, AgentRunner, agent_profile
from .client import Client, connect
from .context import Context
from .dependencies.utils import get_input_model, get_parameters, inject
from .exceptions import SandboxTimeoutError, TaskError
from .kits import Kit, KitCache, KitPackage
from .models import Workspace
from .network import Network
from .params import Mounted, Uploaded, WorkspaceDir
from .tasks import Task
from .utils import PerLoop, as_coroutine, parse_timeout, unique_name

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
    from datetime import timedelta

    from .models import Created
    from .sandbox import Sandbox
    from .types import Lifespan, ProgressHandler


__all__ = ["FastSandbox", "run"]


class FastSandbox:
    """An application of tasks that run in sandboxes.

    Run its tasks with `await app.run(name, **arguments)`, from synchronous code
    with `app.run_sync`, or from the command line with `fastsandbox run`. Use
    it as an async context manager to run several tasks with one client and one
    lifespan; otherwise each run opens its own.
    """

    def __init__(
        self,
        name: str = "fastsandbox",
        *,
        lifespan: Lifespan | None = None,
        kit: Kit | KitPackage | str = "shell",
        kits: KitCache | None = None,
        client: Client | None = None,
        socket: str | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        """An application.

        Args:
            name: The name of the application, the prefix of its sandboxes.
            lifespan: Run around the life of the application; what it yields
                is `Context.state`.
            kit: The kit of tasks that do not name one.
            kits: The kit cache; the one of the process otherwise (`KitCache.default()`),
                which forges kits without the `sbx` CLI and keeps them in memory.
            client: A client to use instead of connecting.
            socket: The socket to connect to, when `client` is not given.
            max_concurrency: How many runs may hold a sandbox at once.
        """
        self.name = name
        self.tasks: dict[str, Task] = {}
        self.state: Mapping[str, Any] = {}
        self._lifespan = lifespan
        self._kit = kit
        self._kits = kits
        self._client = client
        self._socket = socket
        self._semaphore = _limit(max_concurrency)
        self._stack: contextlib.AsyncExitStack | None = None
        self._active: Client | None = None

    # Declaration.

    @overload
    def task(self, fn: Callable[..., Any], /) -> Task: ...

    @overload
    def task(
        self,
        fn: None = None,
        *,
        name: str | None = None,
        kit: Kit | KitPackage | str | None = None,
        network: Network | None = None,
        timeout: float | str | timedelta | None = None,
        env: Mapping[str, str] | None = None,
        cpus: int | None = None,
        memory: str | None = None,
        keep: bool = False,
        description: str | None = None,
        max_concurrency: int | None = None,
    ) -> Callable[[Callable[..., Any]], Task]: ...

    def task(
        self,
        fn: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        kit: Kit | KitPackage | str | None = None,
        network: Network | None = None,
        timeout: float | str | timedelta | None = None,
        env: Mapping[str, str] | None = None,
        cpus: int | None = None,
        memory: str | None = None,
        keep: bool = False,
        description: str | None = None,
        max_concurrency: int | None = None,
    ) -> Task | Callable[[Callable[..., Any]], Task]:
        """Declares a task; use it as `@app.task` or `@app.task(...)`.

        Args:
            fn: The function, when used without arguments.
            name: The name of the task; the name of the function by default.
            kit: The kit of its sandbox; the kit of the application by default.
            network: The network rules of its sandbox.
            timeout: The deadline of a run: seconds, a `timedelta` or e.g. `"10m"`.
            env: Environment variables of its sandbox.
            cpus: Number of virtual CPUs.
            memory: Memory limit, e.g. `4g`.
            keep: Keeps the sandbox after the run, for debugging.
            description: Its documentation; the docstring by default.
            max_concurrency: How many runs of this task may run at once.
        """
        localns = sys._getframe(1).f_locals

        def register(fn: Callable[..., Any]) -> Task:
            return self._register(
                fn,
                localns=localns,
                name=name,
                kit=kit,
                network=network,
                timeout=timeout,
                env=env,
                cpus=cpus,
                memory=memory,
                keep=keep,
                description=description,
                max_concurrency=max_concurrency,
                agent=None,
                allow_agent_hosts=False,
            )

        return register(fn) if fn is not None else register

    def agent(
        self,
        agent: str,
        *,
        name: str | None = None,
        kit: Kit | str | None = None,
        network: Network | None = None,
        allow_agent_hosts: bool = True,
        timeout: float | str | timedelta | None = None,
        env: Mapping[str, str] | None = None,
        cpus: int | None = None,
        memory: str | None = None,
        keep: bool = False,
        description: str | None = None,
        max_concurrency: int | None = None,
    ) -> Callable[[Callable[..., Any]], Task]:
        """Declares a task whose sandbox runs a coding agent, reached with `ctx.agent`.

        `agent` is one of `claude`, `codex`, `copilot`, `cursor`, `devin`, `docker-agent`,
        `droid`, `kiro` or `opencode`.

        The credentials of the agent are read from the environment (e.g.
        `ANTHROPIC_API_KEY`) and pushed as secrets of its sandbox only.

        Args:
            agent: The agent.
            name: The name of the task; the name of the function by default.
            kit: The kit, the agent's own by default, e.g. composed with mixins.
            network: The network rules of its sandbox.
            allow_agent_hosts: Allows the hosts the agent needs along with
                `network`, when `network` is given.
            timeout: The deadline of a run.
            env: Environment variables of its sandbox.
            cpus: Number of virtual CPUs.
            memory: Memory limit, e.g. `4g`.
            keep: Keeps the sandbox after the run, for debugging.
            description: Its documentation; the docstring by default.
            max_concurrency: How many runs of this task may run at once.

        """
        profile = agent_profile(agent)
        localns = sys._getframe(1).f_locals

        def register(fn: Callable[..., Any]) -> Task:
            return self._register(
                fn,
                localns=localns,
                name=name,
                kit=kit if kit is not None else Kit(base=profile.name),
                network=network,
                timeout=timeout,
                env=env,
                cpus=cpus,
                memory=memory,
                keep=keep,
                description=description,
                max_concurrency=max_concurrency,
                agent=profile,
                allow_agent_hosts=allow_agent_hosts,
            )

        return register

    def _register(
        self,
        fn: Callable[..., Any],
        *,
        localns: Mapping[str, Any],
        name: str | None,
        kit: Kit | KitPackage | str | None,
        network: Network | None,
        timeout: float | str | timedelta | None,
        env: Mapping[str, str] | None,
        cpus: int | None,
        memory: str | None,
        keep: bool,
        description: str | None,
        max_concurrency: int | None,
        agent: AgentProfile | None,
        allow_agent_hosts: bool,
    ) -> Task:
        """Builds and registers a task."""
        task_name = name or fn.__name__
        if task_name in self.tasks:
            raise TaskError(f"a task named {task_name!r} is already declared")
        parameters = get_parameters(fn, localns)
        hints = get_type_hints(fn, localns=dict(localns), include_extras=True)
        returned = hints.get("return", inspect.Signature.empty)
        output = (
            None
            if returned in (inspect.Signature.empty, None, type(None))
            else TypeAdapter(returned)
        )
        task = Task(
            app=self,
            name=task_name,
            fn=fn,
            description=description or inspect.getdoc(fn) or "",
            kit=kit if kit is not None else self._kit,
            network=network or Network(),
            timeout=parse_timeout(timeout),
            env=dict(env or {}),
            cpus=cpus,
            memory=memory,
            keep=keep,
            agent=agent,
            allow_agent_hosts=allow_agent_hosts,
            parameters=parameters,
            input_model=get_input_model(task_name, fn, parameters),
            output=output,
            semaphore=_limit(max_concurrency),
        )
        self.tasks[task_name] = task
        return task

    # Life cycle.

    async def _open(self, stack: contextlib.AsyncExitStack) -> tuple[Client, Mapping[str, Any]]:
        """Connects (unless a client was given) and enters the lifespan on `stack`."""
        client = self._client or await connect(self._socket)
        if self._kits is not None:
            client = Client(client.native, kits=self._kits)
        state: Mapping[str, Any] = {}
        if self._lifespan is not None:
            yielded = await stack.enter_async_context(self._lifespan(self))
            state = dict(yielded) if yielded is not None else {}
        return client, state

    async def __aenter__(self) -> FastSandbox:
        if self._stack is not None:
            raise TaskError(f"application {self.name} is already started")
        stack = contextlib.AsyncExitStack()
        try:
            client, state = await self._open(stack)
        except BaseException:
            await stack.aclose()
            raise
        self._stack, self._active, self.state = stack, client, state
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        stack, self._stack, self._active, self.state = self._stack, None, None, {}
        if stack is not None:
            await stack.aclose()

    @contextlib.asynccontextmanager
    async def _session(self) -> AsyncIterator[tuple[Client, Mapping[str, Any]]]:
        """The client and lifespan state of a run.

        Those of the started application, or ones opened for this run alone.
        """
        if self._active is not None:
            yield self._active, self.state
            return
        async with contextlib.AsyncExitStack() as stack:
            yield await self._open(stack)

    # Running.

    def get_task(self, task: str | Task) -> Task:
        """The task `task`.

        Raises:
            TaskError: When the application has no such task.
        """
        if isinstance(task, Task):
            return task
        try:
            return self.tasks[task]
        except KeyError:
            known = ", ".join(sorted(self.tasks)) or "none"
            raise TaskError(f"unknown task {task!r}: the tasks are {known}") from None

    async def run(
        self, task: str | Task, /, *, on_progress: ProgressHandler | None = None, **arguments: Any
    ) -> Any:
        """Runs a task in a throw-away sandbox and returns its validated result.

        Args:
            task: The task, or its name.
            on_progress: Receives what the task reports with
                `Context.report_progress`.
            **arguments: The inputs of the task, validated by its signature.

        Raises:
            pydantic.ValidationError: When the inputs or the result do not
                match the signature of the task.
            SandboxTimeoutError: When the run goes over the timeout of the task.
        """
        task = self.get_task(task)
        inputs = task.input_model.model_validate(arguments)
        values = {name: getattr(inputs, name) for name in type(inputs).model_fields}
        async with contextlib.AsyncExitStack() as limits:
            for semaphore in (self._semaphore, task.semaphore):
                if semaphore is not None:
                    await limits.enter_async_context(semaphore.get())
            async with self._session() as (client, state):
                result = await self._run_in_sandbox(client, state, task, values, on_progress)
        return task.output.validate_python(result) if task.output is not None else result

    def run_sync(self, task: str | Task, /, **arguments: Any) -> Any:
        """Runs a task from synchronous code (see `run`)."""
        return asyncio.run(self.run(task, **arguments))

    async def _run_in_sandbox(
        self,
        client: Client,
        state: Mapping[str, Any],
        task: Task,
        values: dict[str, Any],
        on_progress: ProgressHandler | None,
    ) -> Any:
        """Creates the sandbox of a run, prepares it, runs the task in it."""
        package = await client.package(task.kit)
        workspace, clone, mounts, uploads = self._host_paths(task, values)
        creation = client.create(
            unique_name(_slug(f"{self.name}-{task.name}")),
            kit=package,
            workspace=workspace,
            clone=clone,
            workspaces=mounts,
            env=task.env,
            cpus=task.cpus,
            memory=task.memory,
        )
        sandbox = await creation
        try:
            async with sandbox.running():
                await self._prepare(client, task, sandbox, package, uploads, creation.created)
                agent = None
                if task.agent is not None:
                    described = package.agent
                    if described is None:
                        raise TaskError(f"the kit of task {task.name} describes no agent")
                    agent = AgentRunner(sandbox, task.agent, described)
                context = Context(
                    self,
                    task,
                    client,
                    sandbox,
                    agent,
                    state,
                    asyncio.get_running_loop(),
                    on_progress,
                )
                return await self._call(task, context, values)
        finally:
            if not task.keep:
                with contextlib.suppress(Exception):
                    await sandbox.force_delete()

    @staticmethod
    def _host_paths(
        task: Task, values: dict[str, Any]
    ) -> tuple[str | None, bool, list[Workspace], list[tuple[str, str]]]:
        """The workspace, mounts and uploads the markers of the inputs ask for."""
        workspace: str | None = None
        clone = False
        mounts: list[Workspace] = []
        uploads: list[tuple[str, str]] = []
        for parameter in task.parameters:
            marker = parameter.marker
            value = values.get(parameter.name)
            if parameter.kind != "input" or marker is None or value is None:
                continue
            path = str(Path(value).expanduser().resolve())
            if isinstance(marker, WorkspaceDir):
                if workspace is not None:
                    raise TaskError(f"task {task.name} has more than one WorkspaceDir")
                workspace, clone = path, marker.clone
            elif isinstance(marker, Mounted):
                mounts.append(Workspace(dir=path, read_only=marker.read_only, target=marker.target))
            elif isinstance(marker, Uploaded):
                uploads.append((path, marker.target))
        return workspace, clone, mounts, uploads

    @staticmethod
    async def _prepare(
        client: Client,
        task: Task,
        sandbox: Sandbox,
        package: KitPackage,
        uploads: list[tuple[str, str]],
        created: Created | None,
    ) -> None:
        """Applies the network rules, pushes the agent credentials, uploads.

        The credentials the daemon withholds, at the creation of the sandbox (`created`) or
        when a credential is pushed, are logged as a warning: the proxy injects nothing for
        them, and an agent without its credential fails later, for no reason it can give.
        """
        network = task.network
        if task.agent is not None and task.allow_agent_hosts and network.changes:
            described = package.agent
            hosts = described.hosts() if described is not None else []
            if hosts:
                network = Network.allow(*hosts) | network
        await network.apply(sandbox)
        withheld = set(created.withheld) if created is not None else set()
        pushed: set[str] = set()
        if task.agent is not None:
            for service, value in task.agent.found_credentials():
                outcome = await sandbox.push_service_secret(service, value)
                withheld.update(outcome.withheld)
                pushed.add(service)
        if withheld:
            _report_withheld(task, sandbox, withheld, pushed)
        if uploads:
            # The target may lie where only root can create it (`/work`): make
            # it as root, owned by the default user of the kit.
            owner = (await sandbox.exec("echo $(id -u):$(id -g)", check=True)).stdout.strip()
            for host_path, target in uploads:
                await sandbox.exec(
                    ["sh", "-c", 'mkdir -p "$1" && chown "$2" "$1"', "sh", target, owner],
                    user="0",
                    check=True,
                )
                archive = await asyncio.to_thread(_contents_archive, host_path)
                await sandbox.upload_archive(target, archive)

    async def _call(self, task: Task, context: Context, values: dict[str, Any]) -> Any:
        """Resolves the injected parameters and calls the task function."""
        async with contextlib.AsyncExitStack() as stack:
            cache: dict[Callable[..., Any], Any] = {}
            arguments = {}
            for parameter in task.parameters:
                if parameter.kind == "input":
                    arguments[parameter.name] = values[parameter.name]
                else:
                    arguments[parameter.name] = await inject(parameter, context, stack, cache)
            try:
                async with asyncio.timeout(task.timeout):
                    if inspect.iscoroutinefunction(task.fn):
                        return await task.fn(**arguments)
                    return await asyncio.to_thread(functools.partial(task.fn, **arguments))
            except TimeoutError:
                raise SandboxTimeoutError(
                    f"task {task.name} ran over {task.timeout}s",
                    operation="task run",
                    after=task.timeout,
                ) from None

    def __repr__(self) -> str:
        return f"FastSandbox(name={self.name!r}, tasks={sorted(self.tasks)!r})"


def _contents_archive(directory: str) -> bytes:
    """A tar archive of the contents of `directory`, at the root of the archive."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for entry in sorted(Path(directory).iterdir()):
            archive.add(entry, arcname=entry.name)
    return buffer.getvalue()


def _limit(max_concurrency: int | None) -> PerLoop[asyncio.Semaphore] | None:
    """The bound of `max_concurrency` runs at once, if any, a semaphore per event loop."""
    if not max_concurrency:
        return None
    return PerLoop(functools.partial(asyncio.Semaphore, max_concurrency))


def _slug(text: str) -> str:
    """`text` as a sandbox name prefix: lowercase letters, digits and dashes."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "task"


def _report_withheld(task: Task, sandbox: Sandbox, withheld: set[str], pushed: set[str]) -> None:
    """Logs the credentials the daemon withholds from the sandbox of a run of `task`.

    The warning goes to the logger of the task, `fastsandbox.task.<name>`, and names the
    credentials pushed from the environment among them: the daemon accepted those pushes,
    and gives their values to nobody.
    """
    lost = sorted(withheld & pushed)
    logging.getLogger(f"fastsandbox.task.{task.name}").warning(
        "%s [%s] the daemon withholds the credentials %s, which the kits of the sandbox "
        "declare: the proxy injects nothing for them%s",
        task.name,
        sandbox.name,
        ", ".join(sorted(withheld)),
        f", the values pushed from the environment for {', '.join(lost)} included" if lost else "",
    )


def run[T](target: Task | Awaitable[T], /, **arguments: Any) -> Any:
    """Runs a task, or any awaitable, from synchronous code.

    For a script, a notebook cell or a test.

    Example:
        >>> fastsandbox.run(run_tests, repo=".")
        >>> fastsandbox.run(main())

    """
    if isinstance(target, Task):
        return target.app.run_sync(target, **arguments)
    return asyncio.run(as_coroutine(target))

"""The `fastsandbox` command line.

    fastsandbox run [APP] TASK [--param VALUE ...]   run a task, print its result
    fastsandbox tasks [APP]                          list the tasks and their inputs
    fastsandbox info                                 the daemon, its version, the socket
    fastsandbox kits compile KIT [--mixin M] [--arg K=V]
                                                     compile a kit into the cache
    fastsandbox ssh-proxy SANDBOX                    an OpenSSH ProxyCommand

`APP` is `path/to/file.py[:name]` or `package.module[:name]`; by default the
`app` key of `[tool.fastsandbox]` in `pyproject.toml`, else `app.py`, else
`main.py`. Without `:name`, the application is the module's only FastSandbox
instance, or the one named `app`.

The inputs of a task become options: `--repo .`, `--issue "..."`; booleans are
`--flag` / `--no-flag`, lists and dictionaries are JSON; `--input '{...}'`
gives them all as one JSON object.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib
import importlib.util
import json
import logging
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .applications import FastSandbox
from .client import connect
from .exceptions import SandboxError
from .kits import Kit, KitCache

if TYPE_CHECKING:
    from .tasks import Task

__all__ = ["load_app", "main"]


def _default_app() -> str:
    """The application named by `pyproject.toml`, else `app.py`, else `main.py`."""
    pyproject = Path("pyproject.toml")
    if pyproject.is_file():
        config = tomllib.loads(pyproject.read_text()).get("tool", {}).get("fastsandbox", {})
        if isinstance(config.get("app"), str):
            return str(config["app"])
    for candidate in ("app.py", "main.py"):
        if Path(candidate).is_file():
            return candidate
    raise SystemExit("no application given and no app.py, main.py or [tool.fastsandbox] app")


def load_app(spec: str | None = None) -> FastSandbox:
    """The application `spec` names (see the module documentation)."""
    spec = spec or _default_app()
    target, _, attribute = spec.partition(":")
    if target.endswith(".py") or Path(target).is_file():
        path = Path(target).resolve()
        sys.path.insert(0, str(path.parent))
        module_spec = importlib.util.spec_from_file_location(path.stem, path)
        if module_spec is None or module_spec.loader is None:
            raise SystemExit(f"cannot load {target}")
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[path.stem] = module
        module_spec.loader.exec_module(module)
    else:
        sys.path.insert(0, str(Path.cwd()))
        module = importlib.import_module(target)
    if attribute:
        app = getattr(module, attribute, None)
    else:
        apps = [value for value in vars(module).values() if isinstance(value, FastSandbox)]
        named = getattr(module, "app", None)
        app = named if isinstance(named, FastSandbox) else (apps[0] if len(apps) == 1 else None)
    if not isinstance(app, FastSandbox):
        raise SystemExit(f"no FastSandbox application found in {spec}")
    return app


def _task_parser(task: Task) -> argparse.ArgumentParser:
    """The options of the inputs of `task`."""
    parser = argparse.ArgumentParser(
        prog=f"fastsandbox run {task.name}", description=task.description or None
    )
    parser.add_argument("--input", help="every input, as one JSON object")
    for name, info in task.input_model.model_fields.items():
        flag = "--" + name.replace("_", "-")
        required = info.is_required()
        hint = "" if required else f" (default: {info.default!r})"
        if info.annotation is bool:
            parser.add_argument(flag, dest=name, action=argparse.BooleanOptionalAction)
        else:
            parser.add_argument(flag, dest=name, metavar=name.upper(), help=f"{name}{hint}")
    return parser


def _arguments(task: Task, argv: list[str]) -> dict[str, Any]:
    """The inputs of `task` read from the command line."""
    options = vars(_task_parser(task).parse_args(argv))
    arguments: dict[str, Any] = json.loads(options.pop("input") or "{}")
    for name, value in options.items():
        if value is None:
            continue
        if isinstance(value, str) and value[:1] in ("[", "{"):
            with contextlib.suppress(ValueError):
                value = json.loads(value)
        arguments[name] = value
    return arguments


def _print_result(result: Any) -> None:
    """Prints a result as JSON when it can, as text otherwise."""
    if isinstance(result, BaseModel):
        print(result.model_dump_json(indent=2))
    elif isinstance(result, str):
        print(result)
    elif result is not None:
        try:
            print(json.dumps(result, indent=2, default=str))
        except TypeError:
            print(repr(result))


def _run(app_spec: str | None, task_name: str, argv: list[str]) -> int:
    """`fastsandbox run`."""
    app = load_app(app_spec)
    task = app.get_task(task_name)
    arguments = _arguments(task, argv)
    _print_result(app.run_sync(task, **arguments))
    return 0


def _tasks(app_spec: str | None) -> int:
    """`fastsandbox tasks`."""
    app = load_app(app_spec)
    for task in app.tasks.values():
        kind = f"agent {task.agent.name}" if task.agent is not None else "task"
        print(f"{task.name}  ({kind}, kit {getattr(task.kit, 'label', task.kit)})")
        if task.description:
            print("    " + task.description.splitlines()[0])
        for name, info in task.input_model.model_fields.items():
            default = "required" if info.is_required() else f"default {info.default!r}"
            annotation = getattr(info.annotation, "__name__", str(info.annotation))
            print(f"    --{name.replace('_', '-')}  {annotation}, {default}")
    return 0


async def _info() -> int:
    """`fastsandbox info`."""
    from . import SUPPORTED_API

    client = await connect(version_policy="warn")
    health = client.health
    print(f"socket       {client.socket_path}")
    print(f"sbx          {health.version} ({health.status})")
    print(f"api          {health.api_version} (supported {SUPPORTED_API[0]} to {SUPPORTED_API[1]})")
    print(f"sandboxes    {len(await client.sandboxes.list())}")
    print(f"kit cache    {client.kits.directory or 'memory, kits forged without the sbx CLI'}")
    return 0


async def _compile(kit: str, mixins: list[str], args: list[str]) -> int:
    """`fastsandbox kits compile`: compiles a kit with the `sbx` CLI into the kit cache."""
    pairs = dict(arg.split("=", 1) for arg in args)
    client = await connect()
    composition = Kit(base=kit, mixins=tuple(mixins), args=pairs)
    package = await KitCache(sbx="sbx").package(client, composition)
    print(f"{composition.label}: {package.dir}")
    return 0


async def _ssh_proxy(name: str) -> int:
    """`fastsandbox ssh-proxy`: relays stdin and stdout to the sandbox SSH server.

    The sandbox is held running meanwhile.
    """
    client = await connect()
    sandbox = client.sandbox(name)
    async with sandbox.running():
        tunnel = await sandbox.ssh_tunnel()
        await tunnel.proxy_stdio()
    return 0


def _parser() -> argparse.ArgumentParser:
    """The top-level parser."""
    parser = argparse.ArgumentParser(
        prog="fastsandbox", description="Docker Sandboxes for Python: run tasks in sandboxes."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log what fastsandbox does")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run a task", add_help=False)
    run.add_argument("target", nargs="+", help="[APP] TASK")
    commands.add_parser("tasks", help="list the tasks").add_argument("app", nargs="?")
    commands.add_parser("info", help="the daemon and the socket")
    kits = commands.add_parser("kits", help="kit packages").add_subparsers(
        dest="kits_command", required=True
    )
    compile_ = kits.add_parser("compile", help="compile a kit with the sbx CLI into the cache")
    compile_.add_argument("kit")
    compile_.add_argument("--mixin", action="append", default=[])
    compile_.add_argument("--arg", action="append", default=[], metavar="NAME=VALUE")
    commands.add_parser("ssh-proxy", help="an OpenSSH ProxyCommand").add_argument("sandbox")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Runs the command line; returns the exit status."""
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    known, rest = parser.parse_known_args(argv)
    logging.basicConfig(level=logging.INFO if known.verbose else logging.WARNING)
    try:
        if known.command == "run":
            target = list(known.target)
            # `run APP TASK` or `run TASK`: an option-less first word naming a
            # file or a module with a colon is the application.
            first = target[0]
            if len(target) > 1 and (":" in first or first.endswith(".py") or Path(first).is_file()):
                return _run(first, target[1], target[2:] + rest)
            return _run(None, first, target[1:] + rest)
        if rest:
            parser.error(f"unrecognized arguments: {' '.join(rest)}")
        if known.command == "tasks":
            return _tasks(known.app)
        if known.command == "info":
            return asyncio.run(_info())
        if known.command == "kits":
            return asyncio.run(_compile(known.kit, known.mixin, known.arg))
        if known.command == "ssh-proxy":
            return asyncio.run(_ssh_proxy(known.sandbox))
    except SandboxError as err:
        print(f"fastsandbox: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

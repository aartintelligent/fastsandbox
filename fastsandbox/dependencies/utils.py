"""The analysis of task signatures and the resolution of injected parameters."""

from __future__ import annotations

import contextlib
import inspect
import re
from typing import TYPE_CHECKING, Annotated, Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel, ConfigDict, create_model

from ..exceptions import TaskError
from ..params import Depends, Mounted, Uploaded, WorkspaceDir
from .models import Parameter

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from ..context import Context

__all__ = [
    "get_input_model",
    "get_parameters",
    "inject",
    "injected_kind",
    "resolve",
    "split_annotated",
]


def split_annotated(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    """The type and the metadata of an `Annotated` annotation."""
    if get_origin(annotation) is Annotated:
        base, *metadata = get_args(annotation)
        return base, tuple(metadata)
    return annotation, ()


def injected_kind(annotation: Any) -> str | None:
    """The injection a type stands for, if any."""
    # Imported here: these modules import the framework in turn.
    from ..agents import AgentRunner
    from ..client import Client
    from ..context import Context
    from ..sandbox import Sandbox

    for kind, cls in (
        ("context", Context),
        ("sandbox", Sandbox),
        ("client", Client),
        ("agent", AgentRunner),
    ):
        if isinstance(annotation, type) and issubclass(annotation, cls):
            return kind
    return None


def get_parameters(
    fn: Callable[..., Any], localns: Mapping[str, Any] | None = None
) -> list[Parameter]:
    """The parameters of `fn`, classified.

    `localns` is the namespace `fn` was declared in, for annotations that name
    local objects, such as a dependency defined in the same function.
    """
    hints = get_type_hints(fn, localns=dict(localns or {}), include_extras=True)
    parameters = []
    for name, parameter in inspect.signature(fn).parameters.items():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            raise TaskError(f"{fn.__qualname__}: *args and **kwargs are not supported")
        annotation = hints.get(name, Any)
        base, metadata = split_annotated(annotation)
        depends = next((m for m in metadata if isinstance(m, Depends)), None)
        marker = next(
            (m for m in metadata if isinstance(m, WorkspaceDir | Mounted | Uploaded)), None
        )
        if depends is not None:
            parameters.append(Parameter(name, "depends", base, depends))
        elif (kind := injected_kind(base)) is not None:
            parameters.append(Parameter(name, kind, base))
        else:
            parameters.append(Parameter(name, "input", annotation, marker))
    return parameters


def get_input_model(
    name: str, fn: Callable[..., Any], parameters: list[Parameter]
) -> type[BaseModel]:
    """The Pydantic model of the inputs of a task."""
    signature = inspect.signature(fn)
    fields: dict[str, Any] = {}
    for parameter in parameters:
        if parameter.kind != "input":
            continue
        default = signature.parameters[parameter.name].default
        fields[parameter.name] = (
            parameter.annotation,
            ... if default is inspect.Parameter.empty else default,
        )
    model_name = "".join(part.title() for part in re.split(r"[^A-Za-z0-9]+", name)) + "Input"
    return create_model(model_name, __config__=ConfigDict(extra="forbid"), **fields)


async def inject(
    parameter: Parameter,
    context: Context,
    stack: contextlib.AsyncExitStack,
    cache: dict[Callable[..., Any], Any],
) -> Any:
    """The value of an injected parameter."""
    if parameter.kind == "context":
        return context
    if parameter.kind == "sandbox":
        return context.sandbox
    if parameter.kind == "client":
        return context.client
    if parameter.kind == "agent":
        return context.agent
    depends: Depends = parameter.marker
    return await resolve(depends, context, stack, cache)


async def resolve(
    depends: Depends,
    context: Context,
    stack: contextlib.AsyncExitStack,
    cache: dict[Callable[..., Any], Any],
) -> Any:
    """Calls a dependency, its own dependencies first."""
    if depends.use_cache and depends.dependency in cache:
        return cache[depends.dependency]
    arguments = {}
    for parameter in get_parameters(depends.dependency):
        if parameter.kind == "input":
            raise TaskError(
                f"dependency {depends.dependency.__qualname__} takes a plain parameter "
                f"{parameter.name!r}: only Context, Sandbox, Client, AgentRunner and Depends"
            )
        arguments[parameter.name] = await inject(parameter, context, stack, cache)
    fn = depends.dependency
    if inspect.isasyncgenfunction(fn):
        value = await stack.enter_async_context(contextlib.asynccontextmanager(fn)(**arguments))
    elif inspect.isgeneratorfunction(fn):
        value = stack.enter_context(contextlib.contextmanager(fn)(**arguments))
    elif inspect.iscoroutinefunction(fn):
        value = await fn(**arguments)
    else:
        value = fn(**arguments)
    if depends.use_cache:
        cache[fn] = value
    return value

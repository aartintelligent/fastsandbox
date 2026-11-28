"""Testing without the daemon.

A fake `sandboxd` on a Unix socket, and kit packages that need no `sbx` CLI.

`FakeDaemon` speaks enough of the daemon API for the client and FastSandbox:
health, the life cycle of sandboxes, held sessions, command execution,
network rules, credentials, files, image loading, and the pulls and exports of
the published kits `shell` and `claude` with the kit settings, so that kits
are forged without the CLI as they are by default. Its state is in memory
and every request is recorded. Replace or add a route with `route`, and decide
what commands print with `on_exec`.

Example:
    >>> async with FakeDaemon() as daemon:
    ...     daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout="ok"))
    ...     app = FastSandbox(socket=str(daemon.socket_path), kit=fake_package(tmp_path))
    ...     await app.run("my_task")

Interactive sessions and SSH tunnels upgrade the connection; the fake answers
them with `501`, so code that uses them needs the real daemon.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import io
import json
import re
import shutil
import tarfile
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Self
from urllib.parse import parse_qs, unquote, urlsplit

from .kits import KitPackage
from .models import ExecOutput

__all__ = ["FakeDaemon", "PublishedKit", "Request", "Response", "fake_package"]

DESCRIPTOR_ANNOTATION = "vnd.docker.sandbox.kit.descriptor"
"""The annotation of the image index of a published kit that holds its descriptor."""

_REASONS = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    404: "Not Found",
    409: "Conflict",
    500: "Internal Server Error",
    501: "Not Implemented",
}


@dataclass
class Request:
    """A request the fake daemon received.

    Attributes:
        method: HTTP method.
        path: Path, without the query string.
        query: Query parameters, the last value of each.
        headers: Headers, lowercase names.
        body: Raw body.
        params: Parameters of the matched route, e.g. `{"name": "job-42"}`.
    """

    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: bytes
    params: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        """The body, decoded as JSON (`None` when empty)."""
        return json.loads(self.body) if self.body else None


@dataclass
class Response:
    """An answer of the fake daemon.

    Attributes:
        status: HTTP status.
        body: A JSON value, sent as JSON.
        lines: JSON values sent as an NDJSON stream instead of `body`.
        hold: Keeps the (empty) streamed body open until the client leaves,
            as the daemon does for a session.
        raw: Bytes sent as they are instead of `body`, e.g. a tar archive.
        content_type: The content type of `raw`.
    """

    status: int = 200
    body: Any = None
    lines: list[Any] | None = None
    hold: bool = False
    raw: bytes | None = None
    content_type: str = "application/octet-stream"


Handler = Callable[[Request], Response | Awaitable[Response]]
"""Answers a request of a route."""

ExecHandler = Callable[[str, list[str]], ExecOutput | Awaitable[ExecOutput]]
"""Decides what a command of `POST /sandbox/{name}/exec` prints and exits with,
from the sandbox name and the command."""


def _message(status: int, message: str) -> Response:
    """An error answer in the shape of the daemon."""
    return Response(status, {"message": message})


class FakeDaemon:
    """A fake `sandboxd` on a Unix socket, for tests.

    Attributes:
        version: The `sbx` version it reports.
        api_version: The API version it reports.
        sandboxes: The sandboxes, by name, in the shape of `GET /sandbox/{name}`.
        rules: The network rules added through it.
        files: The files of the sandboxes, by `(sandbox, absolute path)`: what
            `PUT /sandbox/{name}/files` extracted, and what `GET` archives.
        kits: The published kits it pulls and exports, by repository, e.g.
            `docker.io/sbx/shell`: `shell` and `claude` at first.
        settings: The daemon settings it knows, by key; an unknown one is a `404`, as the
            daemon answers. The kit settings allow local, unsigned kits at first.
        requests: Every request received, in order.
    """

    def __init__(self, *, version: str = "v0.54.1", api_version: str = "0.52.0") -> None:
        self.version = version
        self.api_version = api_version
        self.sandboxes: dict[str, dict[str, Any]] = {}
        self.rules: list[dict[str, Any]] = []
        self.files: dict[tuple[str, str], bytes] = {}
        self.kits: dict[str, PublishedKit] = published_kits()
        self.settings: dict[str, Any] = {"kit.allowLocalKits": True, "kit.requireSignature": False}
        self.requests: list[Request] = []
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = []
        self._exec: ExecHandler = lambda sandbox, cmd: ExecOutput(exit_code=0)
        self._dir: Path | None = None
        self._server: asyncio.Server | None = None
        self._holds: dict[str, list[asyncio.Event]] = {}
        self._default_routes()

    # Set-up.

    @property
    def socket_path(self) -> Path:
        """The socket to connect to (`fastsandbox.connect(daemon.socket_path)`)."""
        if self._dir is None:
            raise RuntimeError("the fake daemon is not started")
        return self._dir / "sandboxd.sock"

    async def start(self) -> None:
        """Starts listening."""
        self._dir = Path(tempfile.mkdtemp(prefix="fastsandbox-fake-"))
        self._server = await asyncio.start_unix_server(self._serve, path=str(self.socket_path))

    async def stop(self) -> None:
        """Stops listening and closes held sessions."""
        for events in self._holds.values():
            for event in events:
                event.set()
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._server.wait_closed(), 1)
        if self._dir is not None:
            shutil.rmtree(self._dir, ignore_errors=True)
        self._server = None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.stop()

    def route(self, method: str, pattern: str) -> Callable[[Handler], Handler]:
        """Registers a handler for `method` on `pattern`, e.g. `/sandbox/{name}/ports`.

        It comes ahead of the built-in routes.
        """

        def register(handler: Handler) -> Handler:
            self._routes.insert(0, (method.upper(), _compile(pattern), handler))
            return handler

        return register

    def on_exec(self, handler: ExecHandler) -> ExecHandler:
        """Decides what commands print and exit with; usable as a decorator."""
        self._exec = handler
        return handler

    def requests_to(self, method: str, pattern: str) -> list[Request]:
        """The recorded requests matching `method` and `pattern`."""
        regex = _compile(pattern)
        return [r for r in self.requests if r.method == method.upper() and regex.fullmatch(r.path)]

    # Serving.

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Serves the requests of one connection."""
        try:
            while True:
                request = await _read_request(reader)
                if request is None:
                    break
                self.requests.append(request)
                response = await self._dispatch(request)
                await self._send(writer, request, response)
                if response.hold:
                    break
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _dispatch(self, request: Request) -> Response:
        """Finds the handler of a request and calls it."""
        for method, regex, handler in self._routes:
            if method == request.method and (match := regex.fullmatch(request.path)):
                request.params = {k: unquote(v) for k, v in match.groupdict().items()}
                outcome = handler(request)
                return await outcome if asyncio.iscoroutine(outcome) else outcome  # type: ignore[return-value]
        return _message(404, f"no route for {request.method} {request.path}")

    async def _send(
        self, writer: asyncio.StreamWriter, request: Request, response: Response
    ) -> None:
        """Writes a response, streamed when it has lines or holds."""
        reason = _REASONS.get(response.status, "Status")
        head = f"HTTP/1.1 {response.status} {reason}\r\n"
        if response.raw is not None:
            head += f"content-type: {response.content_type}\r\n"
            head += f"content-length: {len(response.raw)}\r\n\r\n"
            writer.write(head.encode() + response.raw)
            await writer.drain()
            return
        if response.lines is None and not response.hold:
            body = json.dumps(response.body if response.body is not None else {}).encode()
            head += f"content-type: application/json\r\ncontent-length: {len(body)}\r\n\r\n"
            writer.write(head.encode() + body)
            await writer.drain()
            return
        head += "content-type: application/x-ndjson\r\ntransfer-encoding: chunked\r\n\r\n"
        writer.write(head.encode())
        for line in response.lines or []:
            data = json.dumps(line).encode() + b"\n"
            writer.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
        await writer.drain()
        if response.hold:
            event = asyncio.Event()
            name = request.params.get("name", "")
            self._holds.setdefault(name, []).append(event)
            closed = asyncio.ensure_future(writer.wait_closed())
            waited = asyncio.ensure_future(event.wait())
            await asyncio.wait({closed, waited}, return_when=asyncio.FIRST_COMPLETED)
            for pending in (closed, waited):
                pending.cancel()
            with contextlib.suppress(ValueError):
                self._holds[name].remove(event)
        writer.write(b"0\r\n\r\n")
        with contextlib.suppress(ConnectionError):
            await writer.drain()

    def _release(self, name: str) -> None:
        """Closes the held sessions of the sandbox `name`."""
        for event in self._holds.pop(name, []):
            event.set()

    # Built-in routes.

    def _default_routes(self) -> None:
        """The routes of the fake daemon."""
        routes: list[tuple[str, str, Handler]] = [
            ("GET", "/daemon/health", self._health),
            ("GET", "/sandbox", lambda r: Response(200, list(self.sandboxes.values()))),
            ("POST", "/sandbox", self._create),
            ("GET", "/sandbox/{name}", self._inspect),
            ("DELETE", "/sandbox/{name}", self._delete),
            ("POST", "/sandbox/{name}/start", lambda r: self._set_status(r, "running")),
            ("POST", "/sandbox/{name}/stop", lambda r: self._set_status(r, "stopped")),
            ("GET", "/sandbox/{name}/session", self._session),
            ("POST", "/sandbox/{name}/exec", self._exec_route),
            ("POST", "/sandbox/{name}/exec/attach", lambda r: _message(501, "not faked")),
            ("POST", "/sandbox/{name}/ssh", lambda r: _message(501, "not faked")),
            ("PUT", "/sandbox/{name}/files", self._put_files),
            ("GET", "/sandbox/{name}/files", self._get_files),
            ("POST", "/sandbox/{name}/credentials", self._credentials),
            ("GET", "/sandbox/{name}/ports", lambda r: self._known(r, lambda s: s["ports"])),
            ("GET", "/policy/network/rules", self._rules),
            ("POST", "/policy/network/rules", self._apply_rules),
            ("POST", "/docker/images/load", lambda r: Response(200, {"message": "image loaded"})),
            ("GET", "/docker/images", lambda r: Response(200, [])),
            ("POST", "/docker/images/create", self._pull),
            ("GET", "/docker/images/export", self._export),
            ("GET", "/daemon/settings/{key}", self._setting),
        ]
        for method, pattern, handler in routes:
            self._routes.append((method, _compile(pattern), handler))

    def _health(self, request: Request) -> Response:
        """`GET /daemon/health`."""
        return Response(
            200,
            {
                "status": "healthy",
                "version": self.version,
                "api_version": self.api_version,
                "release": True,
            },
        )

    def _pull(self, request: Request) -> Response:
        """`POST /docker/images/create`: pulls a published kit of `kits`."""
        reference = request.query.get("fromImage", "")
        if repository(reference) not in self.kits:
            return Response(200, lines=[{"error": f"pull access denied for {reference}"}])
        return Response(200, lines=[{"status": f"Status: Image is up to date for {reference}"}])

    def _export(self, request: Request) -> Response:
        """`GET /docker/images/export`: the image of a published kit of `kits`."""
        reference = request.query.get("name", "")
        kit = self.kits.get(repository(reference))
        if kit is None:
            return _message(404, f"No such image: {reference}")
        return Response(200, raw=kit.export(), content_type="application/x-tar")

    def _setting(self, request: Request) -> Response:
        """`GET /daemon/settings/{key}`: a setting of `settings`."""
        key = unquote(request.params["key"])
        if key not in self.settings:
            return _message(404, f"unknown setting {key}")
        value = self.settings[key]
        kind = {bool: "bool", int: "int", list: "list"}.get(type(value), "string")
        return Response(
            200, {"key": key, "value": value, "default": value, "source": "default", "type": kind}
        )

    def _known(self, request: Request, answer: Callable[[dict[str, Any]], Any]) -> Response:
        """`answer` for the sandbox of the request, or a 404."""
        name = request.params["name"]
        sandbox = self.sandboxes.get(name)
        if sandbox is None:
            return _message(404, f'sandbox "{name}" not found')
        return Response(200, answer(sandbox))

    def _inspect(self, request: Request) -> Response:
        """`GET /sandbox/{name}`."""
        return self._known(request, lambda sandbox: sandbox)

    def _create(self, request: Request) -> Response:
        """`POST /sandbox`: the sandbox runs right after creation."""
        body = request.json() or {}
        name = body.get("name", "")
        if name in self.sandboxes:
            return _message(409, f'sandbox "{name}" already exists')
        sandbox = {
            "id": str(uuid.uuid4()),
            "name": name,
            "agent": body.get("agent", "shell"),
            "status": "running",
            "workspace": body.get("workspace") or "",
            "cpus": body.get("cpus"),
            "memory": body.get("memory"),
            "ports": body.get("ports", []),
            "labels": {},
            "request": body,
        }
        self.sandboxes[name] = sandbox
        created = {k: sandbox[k] for k in ("id", "name", "agent", "status", "workspace")}
        return Response(
            200, lines=[{"progress": "   ✓ fake kit image ready\n"}, {"result": created}]
        )

    def _delete(self, request: Request) -> Response:
        """`DELETE /sandbox/{name}`."""
        name = request.params["name"]
        if self.sandboxes.pop(name, None) is None:
            return _message(404, f'sandbox "{name}" not found')
        self._release(name)
        for key in [key for key in self.files if key[0] == name]:
            del self.files[key]
        return Response(200, {"message": f'sandbox "{name}" deleted'})

    def _set_status(self, request: Request, status: str) -> Response:
        """`POST /sandbox/{name}/start` and `/stop`."""
        response = self._known(request, lambda sandbox: sandbox.update(status=status) or sandbox)
        if status == "stopped":
            self._release(request.params["name"])
        return response

    def _session(self, request: Request) -> Response:
        """`GET /sandbox/{name}/session`: held until the client leaves."""
        if request.params["name"] not in self.sandboxes:
            return _message(404, f'sandbox "{request.params["name"]}" not found')
        return Response(200, hold=True)

    async def _exec_route(self, request: Request) -> Response:
        """`POST /sandbox/{name}/exec`."""
        name = request.params["name"]
        if name not in self.sandboxes:
            return _message(404, f'sandbox "{name}" not found')
        outcome = self._exec(name, list((request.json() or {}).get("cmd", [])))
        output = await outcome if asyncio.iscoroutine(outcome) else outcome
        return Response(200, output.model_dump())  # type: ignore[union-attr]

    def _put_files(self, request: Request) -> Response:
        """`PUT /sandbox/{name}/files`: the files of the archive go in `files`.

        They land under the directory `path` of the query.
        """
        name = request.params["name"]
        if name not in self.sandboxes:
            return _message(404, f'sandbox "{name}" not found')
        directory = PurePosixPath(request.query.get("path", "/"))
        with tarfile.open(fileobj=io.BytesIO(request.body)) as archive:
            for member in archive.getmembers():
                extracted = archive.extractfile(member) if member.isfile() else None
                if extracted is not None:
                    self.files[(name, str(directory / member.name))] = extracted.read()
        return Response(200, {"message": "files copied"})

    def _get_files(self, request: Request) -> Response:
        """`GET /sandbox/{name}/files`: `path`, archived as `docker cp` does.

        The last component of the path is the root of the archive.
        """
        name = request.params["name"]
        if name not in self.sandboxes:
            return _message(404, f'sandbox "{name}" not found')
        path = PurePosixPath(request.query.get("path", "/"))
        entries = {
            str(PurePosixPath(path.name) / PurePosixPath(file).relative_to(path)): data
            for (sandbox, file), data in self.files.items()
            if sandbox == name and PurePosixPath(file).is_relative_to(path)
        }
        if not entries:
            return _message(404, f"{path}: no such file or directory")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for entry, data in sorted(entries.items()):
                info = tarfile.TarInfo(entry.removesuffix("/."))
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return Response(200, raw=buffer.getvalue(), content_type="application/x-tar")

    def _credentials(self, request: Request) -> Response:
        """`POST /sandbox/{name}/credentials`."""
        return self._known(request, lambda sandbox: {"message": "Credentials updated"})

    def _rules(self, request: Request) -> Response:
        """`GET /policy/network/rules`."""
        return Response(200, {"governance_active": False, "rules": self.rules})

    def _apply_rules(self, request: Request) -> Response:
        """`POST /policy/network/rules`: every change applies."""
        results = []
        for change in (request.json() or {}).get("actions", []):
            created = []
            for resource in change.get("resources", []):
                rule_id = str(uuid.uuid4())
                created.append(
                    {
                        "rule_id": rule_id,
                        "resource": resource,
                        "protocols": change.get("protocols", []),
                    }
                )
                self.rules.append(
                    {
                        "id": rule_id,
                        "name": rule_id,
                        "decision": "deny" if "deny" in change["action"] else "allow",
                        "resources": [resource],
                        "sandbox_id": change.get("sandbox_id"),
                        "editable": True,
                    }
                )
            results.append(
                {
                    "action": change["action"],
                    "resources": change.get("resources", []),
                    "sandbox_id": change.get("sandbox_id"),
                    "created": created,
                }
            )
        return Response(200, {"results": results})


def _compile(pattern: str) -> re.Pattern[str]:
    """A route pattern such as `/sandbox/{name}/exec` as a regular expression."""
    regex = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(pattern))
    return re.compile(regex)


async def _read_request(reader: asyncio.StreamReader) -> Request | None:
    """Reads one HTTP/1.1 request, or `None` at the end of the connection."""
    line = await reader.readline()
    if not line:
        return None
    method, target, _ = line.decode("latin-1").split(" ", 2)
    headers: dict[str, str] = {}
    while (header := await reader.readline()) not in (b"\r\n", b"\n", b""):
        name, _, value = header.decode("latin-1").partition(":")
        headers[name.strip().lower()] = value.strip()
    body = b""
    if headers.get("transfer-encoding", "").lower() == "chunked":
        while True:
            size = int((await reader.readline()).split(b";")[0], 16)
            if size == 0:
                await reader.readline()
                break
            body += await reader.readexactly(size)
            await reader.readline()
    elif length := int(headers.get("content-length", "0")):
        body = await reader.readexactly(length)
    url = urlsplit(target)
    query = {key: values[-1] for key, values in parse_qs(url.query).items()}
    return Request(method.upper(), url.path, query, headers, body)


@dataclass
class PublishedKit:
    """A published kit the fake daemon pulls and exports, so that kits are forged from it.

    Attributes:
        descriptor: The kit descriptor its image carries, its `spec.yaml` as JSON.
        entrypoint: The entrypoint of its image.
        cmd: The command of its image.
    """

    descriptor: dict[str, Any]
    entrypoint: list[str] = field(default_factory=list)
    cmd: list[str] = field(default_factory=list)

    def export(self) -> bytes:
        """The image as `GET /docker/images/export` streams it: the small files of its export."""
        annotations = {DESCRIPTOR_ANNOTATION: json.dumps(self.descriptor)}
        index = json.dumps(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.index.v1+json",
                "manifests": [],
                "annotations": annotations,
            }
        ).encode()
        config = json.dumps({"config": {"Entrypoint": self.entrypoint, "Cmd": self.cmd}}).encode()
        digest = hashlib.sha256(index).hexdigest()
        config_path = f"blobs/sha256/{hashlib.sha256(config).hexdigest()}"
        files = {
            f"blobs/sha256/{digest}": index,
            config_path: config,
            "index.json": json.dumps({"manifests": [{"digest": f"sha256:{digest}"}]}).encode(),
            "manifest.json": json.dumps([{"Config": config_path}]).encode(),
        }
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return buffer.getvalue()


def published_kits() -> dict[str, PublishedKit]:
    """The published kits a fake daemon serves at first: `shell`, and `claude`.

    `claude` declares the network and the credential of its agent, and the optional
    `open-url@1` the `sbx` CLI leaves out as unsupported, as the real kit does.
    """
    sbx = {"type": "com.docker.sandbox/sbx@1"}
    claude = [
        sbx,
        {
            "type": "com.docker.sandbox/network-policy@1",
            "config": {"runtime": {"allow": ["api.anthropic.com:443"]}},
        },
        {
            "type": "com.docker.sandbox/credential@1",
            "config": {
                "service": "anthropic",
                "apiKey": {
                    "inject": [
                        {"domain": "api.anthropic.com", "header": "x-api-key", "format": "%s"}
                    ]
                },
            },
        },
        {"type": "com.docker.sandbox/open-url@1", "optional": True},
    ]
    return {
        "docker.io/sbx/shell": PublishedKit(
            {
                "schemaVersion": "3",
                "kind": "workload",
                "displayName": "Shell",
                "capabilities": [sbx],
            },
            entrypoint=["bash", "-c", 'exec "$@"', "bash"],
            cmd=["bash", "-l"],
        ),
        "docker.io/sbx/claude": PublishedKit(
            {
                "schemaVersion": "3",
                "kind": "workload",
                "displayName": "Claude Code",
                "capabilities": claude,
            },
            entrypoint=["claude"],
            cmd=["--dangerously-skip-permissions"],
        ),
    }


def repository(reference: str) -> str:
    """The repository of the image reference `reference`, normalized as Docker does.

    `sbx/shell:latest` and `docker.io/sbx/shell@sha256:…` are `docker.io/sbx/shell`.
    """
    name = reference.split("@", 1)[0]
    last = name.rsplit("/", 1)[-1]
    if ":" in last:
        name = name[: len(name) - len(last)] + last.split(":", 1)[0]
    first = name.split("/", 1)[0]
    if "/" not in name:
        name = f"docker.io/library/{name}"
    elif "." not in first and ":" not in first and first != "localhost":
        name = f"docker.io/{name}"
    return name


def fake_package(
    directory: str | Path,
    *,
    agent: str = "shell",
    sbx_version: str = "v0.54.1",
    artifact: dict[str, Any] | None = None,
) -> KitPackage:
    """A kit package with no image, for the fake daemon.

    It is written into `directory`, and creates sandboxes without the `sbx` CLI.

    Args:
        directory: Where to write the package.
        agent: The agent of its kit, e.g. `shell` or `claude`.
        sbx_version: The `sbx` version it claims to be compiled with.
        artifact: The kit artifact. An agent is described by its `manifest`
            (`name`, `binary`, `runOptions`) and the hosts it needs by
            `caps.network.allow`, e.g. `{"manifest": {"name": "claude",
            "binary": "claude"}, "caps": {"network": {"allow":
            ["api.anthropic.com:443"]}}}`.

    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "name": "{{name}}",
        "agent": agent,
        "kits": [f"docker.io/sbx/{agent}:latest"],
        "kit_artifacts": [artifact or {}],
    }
    (directory / "create-body.json").write_text(json.dumps(body))
    (directory / "kit.json").write_text(
        json.dumps({"base": agent, "compiled_with": {"sbx": sbx_version}, "images": []})
    )
    return KitPackage.open(directory)

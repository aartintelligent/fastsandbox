"""`docs_src/client/images.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon, Request, Response

SHELL = "docker.io/sbx/shell:latest"


async def test_images(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    @fake_environment.route("GET", "/docker/images")
    def images(request: Request) -> Response:
        image = {"repository": "docker.io/sbx/shell", "tag": "latest", "id": "sha256:1", "size": 42}
        return Response(200, [image])

    @fake_environment.route("POST", "/docker/images/create")
    def pull(request: Request) -> Response:
        assert request.query["fromImage"] == SHELL
        return Response(200, lines=[{"status": "Pulling from sbx/shell"}, {"status": "Done"}])

    @fake_environment.route("GET", "/docker/images/inspect")
    def inspect(request: Request) -> Response:
        if request.query["name"] != SHELL:
            return Response(404, {"message": "no such image"})
        return Response(200, {"id": "sha256:1", "user": "agent", "entrypoint": ["/init"]})

    await load_example("client/images.py").main()
    assert capsys.readouterr().out == (
        f"{SHELL} 42 bytes\n"
        "pull: Pulling from sbx/shell\n"
        "pull: Done\n"
        f"{SHELL}: user agent, entrypoint ['/init']\n"
        "unknown image held: False\n"
    )

# my-checks

The checks of a project, run on a copy of it in throw-away sandboxes of
[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/), with
[fastsandbox](https://aartintelligent.github.io/fastsandbox/).

## Requirements

- Docker Sandboxes, installed and running for your user: `sbx version` answers.
- Python 3.14 and [uv](https://docs.astral.sh/uv/).

## Run

```sh
uv sync
uv run fastsandbox run check --repo /path/to/project --command "make test"
```

The project is copied into the sandbox: the copy on your machine is never
touched. The result is printed as JSON.

## Test

```sh
uv run pytest
```

The tests run against the fake daemon of fastsandbox: no sandbox is created.

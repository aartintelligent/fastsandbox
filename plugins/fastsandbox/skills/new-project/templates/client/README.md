# my-probe

A tool that drives [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/)
with the client of [fastsandbox](https://aartintelligent.github.io/fastsandbox/):
it creates a throw-away sandbox, asks it what it runs, and deletes it.

## Requirements

- Docker Sandboxes, installed and running for your user: `sbx version` answers.
- Python 3.14 and [uv](https://docs.astral.sh/uv/).

## Run

```sh
uv sync
uv run python probe.py
```

## Test

```sh
uv run pytest
```

The tests run against the fake daemon of fastsandbox: no sandbox is created.

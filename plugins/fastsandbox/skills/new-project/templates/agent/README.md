# my-agents

Coding agents at work in throw-away sandboxes of
[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/), with
[fastsandbox](https://aartintelligent.github.io/fastsandbox/).

## Requirements

- Docker Sandboxes, installed and running for your user: `sbx version` answers.
- Python 3.14 and [uv](https://docs.astral.sh/uv/).
- The API key of the agent in the environment: `ANTHROPIC_API_KEY` for Claude
  Code. It is pushed to the sandbox of each run only.

## Run

```sh
uv sync
uv run fastsandbox kits compile claude   # once: the first compilation takes minutes
uv run fastsandbox run fix --repo /path/to/repository --issue "the parser drops the last line" > fix.patch
git -C /path/to/repository am "$PWD/fix.patch"
```

The agent works on a private clone of the repository: the repository is not
touched until you apply the patch.

## Test

```sh
uv run pytest
```

The tests need no daemon.

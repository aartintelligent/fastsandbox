# Inputs and outputs

Full page: https://aartintelligent.github.io/fastsandbox/framework/inputs-outputs/

## API

The parameters that are not injected (see dependencies.md) are the inputs. The
decorator builds a Pydantic model from them, with `extra="forbid"`:

- an input without a default is required, one with a default is optional;
- values are validated and converted in Pydantic's lax mode: `repeat="2"`
  becomes `2`, a string becomes a `Path` for a `Path` input;
- constraints in `Annotated` apply: `Annotated[int, Field(ge=1, le=10)]`;
- an argument that names no input is refused;
- a failure raises `pydantic.ValidationError` before the client connects: no
  sandbox is created.

The return annotation validates the result, after the sandbox is deleted:

- a Pydantic model, `dict`, `list`, scalar or any type Pydantic knows; a task
  annotated `-> Model` may return the model or a dict of its fields;
- a mismatch raises `pydantic.ValidationError` to the caller;
- no annotation, or `-> None`: the result is returned as it is.

Schemas, for a program that calls tasks on behalf of something else:

| Property | Value |
|---|---|
| `task.input_schema` | JSON schema of the inputs (`properties`, `required`) |
| `task.output_schema` | JSON schema of the result; None without a return annotation |

On the command line, each input is an option (see cli.md):
`name_with_underscores` is `--name-with-dashes`, a `bool` is `--flag` /
`--no-flag`, a value starting with `[` or `{` is read as JSON, and
`--input '{...}'` gives every input at once (options override its keys).

## Example

```python
from typing import Annotated

from pydantic import BaseModel, Field

from fastsandbox import Context, FastSandbox

app = FastSandbox("text")


class Count(BaseModel):
    lines: int
    words: int
    tags: list[str] = []


@app.task(kit="shell")
async def count(
    ctx: Context,
    text: str,
    repeat: Annotated[int, Field(ge=1, le=10)] = 1,
    tags: list[str] | None = None,
) -> Count:
    """Counts the lines and the words of a text, repeated."""
    await ctx.sandbox.write_file("/tmp/input.txt", text * repeat)
    output = await ctx.sandbox.exec(["wc", "-l", "-w", "/tmp/input.txt"], check=True)
    lines, words, _ = output.stdout.split()
    return Count(lines=int(lines), words=int(words), tags=tags or [])


def schemas() -> tuple[dict[str, object], dict[str, object] | None]:
    task = app.get_task("count")
    return task.input_schema, task.output_schema
```

```sh
fastsandbox run app.py count --text "one two" --repeat 2 --tags '["draft"]'
fastsandbox run app.py count --input '{"text": "one two", "repeat": 2}'
```

## Gotchas

- A `Path` input is the path as the caller gave it (`.` stays `.`). When it is
  mounted (`WorkspaceDir`, `Mounted` without target), the sandbox sees it at its
  absolute host path: use `str(path.resolve())` inside the sandbox.
- `*args` and `**kwargs` are refused with `TaskError` at declaration.
- Results are validated after the sandbox is deleted: a result that does not
  match its annotation is lost with it. Keep the return annotation honest, or
  return a model built inside the task.
- Inputs are plain values sent by the caller; never make a secret an input of
  a task run from the command line (it ends up in the shell history).

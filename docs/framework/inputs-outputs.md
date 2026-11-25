# Inputs and outputs

The parameters of a task that are not injected are its inputs, and its return
annotation is the type of its result. FastSandbox builds a Pydantic model from
the signature, validates the arguments of every run with it before anything is
created, and validates the result against the return annotation. This page
shows what that accepts and refuses, and the schemas it gives.

## Validated inputs

```python title="docs_src/tasks/inputs_outputs.py" hl_lines="10-13 19-22"
--8<-- "docs_src/tasks/inputs_outputs.py"
```

The inputs of `count` are `text`, `repeat` and `tags`: `ctx` is injected (see
[Dependencies](dependencies.md)). For each run:

- An input without a default is required, one with a default is optional.
- Values are validated and converted by Pydantic, in its default lax mode:
  `repeat="2"` becomes `2`, a string becomes a `Path` for a `Path` input.
- Constraints of `Annotated` apply: `Field(ge=1, le=10)` refuses `repeat=0`.
- An argument that names no input is refused: the model forbids extra fields.
- A failed validation raises `pydantic.ValidationError` before the client
  connects: no sandbox is created for invalid inputs.

The function receives the validated values: `repeat` is an `int`, whatever the
caller passed.

!!! note "Path inputs"
    A `Path` input is the path as the caller gave it. When it is marked with
    `WorkspaceDir` or `Mounted`, the host directory is mounted at its absolute
    path: use `path.resolve()` to name it inside the sandbox (see
    [Host paths](host-paths.md)).

Parameters cannot be `*args` or `**kwargs`: declaring such a task raises
[`TaskError`][fastsandbox.exceptions.TaskError].

## Validated results

The return annotation validates what the function returns, after the sandbox is
deleted:

- A Pydantic model, a `dict`, a `list`, a scalar or any type Pydantic knows is
  validated, and converted when it can be: a function annotated `-> Count`
  may return the model or a dictionary of its fields.
- A result that does not match raises `pydantic.ValidationError` to the caller.
- Without a return annotation, or with `-> None`, the result is returned as it
  is.

## Schemas

The input model and the result type are also JSON schemas, for a program that
calls tasks on behalf of something else, such as a tool server:

```python
task = app.get_task("count")
task.input_schema   # {"properties": {"text": ..., "repeat": ..., "tags": ...}, "required": ["text"], ...}
task.output_schema  # the schema of Count; None without a return annotation
```

See [`Task.input_schema`][fastsandbox.Task.input_schema] and
[`Task.output_schema`][fastsandbox.Task.output_schema].

## On the command line

`fastsandbox run` turns the inputs into options, and lets Pydantic validate the
strings it reads:

```sh
fastsandbox run docs_src/tasks/inputs_outputs.py count --text "one two" --repeat 2
fastsandbox run docs_src/tasks/inputs_outputs.py count --text "one two" --tags '["draft", "fr"]'
fastsandbox run docs_src/tasks/inputs_outputs.py count --input '{"text": "one two", "repeat": 2}'
```

- An input `name_with_underscores` is the option `--name-with-dashes`.
- A `bool` input is a pair of flags, `--flag` and `--no-flag`.
- A value that starts with `[` or `{` is read as JSON when it is valid JSON:
  lists and dictionaries are given that way.
- `--input` gives every input as one JSON object; options given along with it
  override its keys.

The result is printed as JSON: a model with its fields, a string as it is.
[Command line](cli.md) has the rest of the command.

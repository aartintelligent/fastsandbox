# Command line

The package installs the `fastsandbox` command, also run as
`python -m fastsandbox`. It runs the tasks of an application, lists them,
reports on the daemon, compiles kits ahead of time, and relays SSH to a
sandbox. This page covers each command and how the command finds the
application.

| Command | What it does |
|---|---|
| `fastsandbox run [APP] TASK [OPTIONS]` | Runs a task and prints its result |
| `fastsandbox tasks [APP]` | Lists the tasks of an application and their inputs |
| `fastsandbox info` | Reports the daemon, its version and the socket |
| `fastsandbox kits compile KIT [--mixin M ...] [--arg NAME=VALUE ...]` | Compiles a kit into the kit cache |
| `fastsandbox ssh-proxy SANDBOX` | Relays SSH to a sandbox, as an OpenSSH `ProxyCommand` |

`-v` (`--verbose`), before the command, logs what fastsandbox does.

## Finding the application

`APP` names the application in one of two forms:

- `path/to/file.py`, or `path/to/file.py:name`, for a file;
- `package.module`, or `package.module:name`, for a module importable from the
  current directory.

Without `:name`, the application is the object named `app` in the module, or
else the only [`FastSandbox`][fastsandbox.FastSandbox] instance it holds.

Without `APP`, the command reads the `app` key of `[tool.fastsandbox]` in the
`pyproject.toml` of the current directory, then looks for `app.py`, then for
`main.py`:

```toml title="pyproject.toml"
[tool.fastsandbox]
app = "ci/tasks.py:app"
```

## Listing the tasks

`fastsandbox tasks` imports the application, without connecting to the daemon,
and lists each task: its kind and kit, the first line of its description, and
its inputs as options, required or with their default. For the task of
[Inputs and outputs](inputs-outputs.md):

```console
$ fastsandbox tasks docs_src/tasks/inputs_outputs.py
count  (task, kit shell)
    Counts the lines and the words of a text, repeated.
    --text  str, required
    --repeat  int, default 1
    --tags  Union, default None
```

## Running a task

`fastsandbox run` runs one task and prints its result: a Pydantic model as
indented JSON, a string as it is, other values as JSON, and nothing for `None`.

```sh
fastsandbox run docs_src/tasks/run_tests.py run_tests --repo .
fastsandbox run docs_src/tasks/inputs_outputs.py count --text "one two" --repeat 2
fastsandbox run ci.tasks:app run_tests --input '{"repo": "."}'
fastsandbox run run_tests --repo .   # the application of pyproject.toml, app.py or main.py
```

The first word after `run` is the application when it ends with `.py`, contains
a `:` or names a file, and another word follows; otherwise it is the task.

The inputs of the task are options, which `--help` after the name of the task
lists:

- `--name-with-dashes` for the input `name_with_underscores`;
- `--flag` and `--no-flag` for a `bool` input;
- a value that starts with `[` or `{` is read as JSON, for lists and
  dictionaries;
- `--input '{...}'` gives every input as one JSON object, which the options
  given along with it override.

The values are strings until the input model validates them: `--repeat 2`
gives `repeat=2` (see [Inputs and outputs](inputs-outputs.md)).

The command exits with status 0 when the task succeeds. An error of fastsandbox,
a [`SandboxError`][fastsandbox.exceptions.SandboxError] such as a `TaskError`,
a failed command or a timeout, is printed as `fastsandbox: <message>` and exits
with status 1; other exceptions, invalid inputs among them, end the command
with their traceback. An interruption with ++ctrl+c++ exits with status 130.

## Reporting on the daemon

`fastsandbox info` connects to the daemon and prints the socket, the version of
`sbx` and its health, the API version of the daemon and the range this release
supports, the number of sandboxes and the directory of the kit cache. A daemon
whose API version is outside the supported range is reported with a warning
instead of an error.

## Compiling a kit

`fastsandbox kits compile KIT` compiles a kit with the `sbx` CLI into the kit
cache, as the first run of a task of that kit would, and prints where:

```sh
fastsandbox kits compile claude
fastsandbox kits compile shell --mixin ./kits/my-mixin --arg NAME=VALUE
```

`--mixin` adds a mixin kit, once per mixin, and `--arg` a kit argument; the
composition is cached apart from the plain kit. See [Kits](../client/kits.md).

## SSH to a sandbox

`fastsandbox ssh-proxy SANDBOX` holds the sandbox running and relays its
standard input and output to the SSH server of the sandbox, through the socket:
it is a `ProxyCommand` for the SSH client of the system, without a published
port or a key.

```sh
ssh -o ProxyCommand="fastsandbox ssh-proxy my-sandbox" agent@my-sandbox
```

The SSH server of a sandbox accepts any user without credentials, `root`
included: whoever can run this command can reach every sandbox. See
[SSH](../client/ssh.md).

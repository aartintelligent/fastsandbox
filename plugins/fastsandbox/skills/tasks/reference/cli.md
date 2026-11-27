# Command line

Full page: https://aartintelligent.github.io/fastsandbox/framework/cli/

## API

```text
fastsandbox [-v] run [APP] TASK [--input JSON] [--<input> VALUE ...]
fastsandbox [-v] tasks [APP]
fastsandbox [-v] info
fastsandbox [-v] kits compile KIT [--mixin PATH ...] [--arg NAME=VALUE ...]
fastsandbox [-v] ssh-proxy SANDBOX
```

| Part | Meaning |
|---|---|
| `-v`, `--verbose` | logs what fastsandbox does, at the info level |
| `APP` | `path/to/file.py[:name]` or `package.module[:name]` |
| default `APP` | the `app` key of `[tool.fastsandbox]` in `pyproject.toml`, else `app.py`, else `main.py` in the current directory |
| no `:name` | the module's variable named `app` if it is a `FastSandbox`, else its only `FastSandbox` instance |

**`run`** runs one task and prints its result: a Pydantic model as indented
JSON, a string as it is, other values as JSON, nothing for `None`.

- The first word after `run` is the application when another word follows and
  it ends with `.py`, contains a `:`, or names a file; otherwise it is the
  task, and the default application is used.
- Each input is an option: `name_with_underscores` is `--name-with-dashes`; a
  `bool` input is `--flag` / `--no-flag`; a value starting with `[` or `{` is
  read as JSON when it is valid JSON; `--input '{...}'` gives every input as
  one JSON object, which the other options override.
- `fastsandbox run APP TASK --help` lists the options of the task.
- Values are strings until the input model validates them (`--repeat 2` gives
  `repeat=2`).

**`tasks`** imports the application without connecting and lists each task:
`name  (task, kit shell)` or `(agent claude, kit claude)`, the first line of its
description, and its inputs with their type and default.

**`info`** connects (with `version_policy="warn"`) and prints the socket, the
version and health of `sbx`, the API version of the daemon and the range this
release supports, the number of sandboxes and the kit cache directory, or
`memory` when kits are forged and kept in memory.

**`kits compile`** compiles a kit with the `sbx` CLI into the kit cache on
disk and prints where: `--mixin` adds a mixin kit (repeatable), `--arg
NAME=VALUE` a kit argument (repeatable); a composition is cached apart from the
plain kit. Tasks forge their kits without the CLI; compiling ahead of time is
for a kit only the CLI resolves, given to an application whose cache compiles
with the CLI (`FastSandbox(kits=KitCache(sbx="sbx"))`).

**`ssh-proxy`** holds the sandbox running and relays standard input and output
to its SSH server through the socket: an OpenSSH `ProxyCommand`.

Exit status: 0 on success; 1 for an error of fastsandbox (a `SandboxError`,
printed as `fastsandbox: <message>` on standard error); 130 on ++ctrl+c++;
other exceptions, invalid inputs among them, end with their traceback. No
application found, or no `app.py`, `main.py` or `[tool.fastsandbox] app`, exits
with a message.

## Example

```python
# app.py, with `[tool.fastsandbox] app = "app.py"` in pyproject.toml or found
# by name in the current directory.
from fastsandbox import Context, FastSandbox

app = FastSandbox("ci")


@app.task(kit="shell")
async def greet(ctx: Context, name: str, loud: bool = False) -> str:
    """Greets someone from inside a sandbox."""
    output = await ctx.sandbox.exec(["echo", f"hello {name}"], check=True)
    text = output.stdout.strip()
    return text.upper() if loud else text
```

```sh
fastsandbox tasks                         # the tasks of app.py and their inputs
fastsandbox run greet --name ada --loud   # the default application
fastsandbox run app.py:app greet --input '{"name": "ada"}'
fastsandbox kits compile ./kits/my-kit    # compile a local kit with the sbx CLI
fastsandbox info                          # the daemon, its version, the socket
ssh -o ProxyCommand="fastsandbox ssh-proxy my-sandbox" agent@my-sandbox
```

## Gotchas

- `fastsandbox info` is the first check when nothing works: it reports a daemon
  that cannot be reached, and a daemon whose API version is outside the
  supported range (as a warning).
- The SSH server of a sandbox accepts any user without credentials, `root`
  included: whoever can run `ssh-proxy` reaches every sandbox of the user.
- Options of `run` are read after the task name; options before it belong to
  `fastsandbox` itself (`-v`).
- A secret passed as an option ends up in the shell history; read secrets from
  the environment in the task or its dependencies instead.

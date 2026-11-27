"""Arguments a kit declares, chosen when it is forged: the model and the effort of `claude`.

A kit declares its arguments with a default, a description and a pattern or a
list of values; the `claude` kit declares `model` and `reasoningEffort`. The
forge checks their values as the `sbx` CLI does and resolves them into the kit
artifact, as `sbx create --kit-arg model=…` does (`Kit(args=…)`, here through
`common.kit.package`): the sandbox gets them as environment variables, and the
install command of the kit writes them into `~/.claude/settings.json`. A value
the kit refuses is an `InvalidKitError` before anything is created. A program
that offers a choice of model makes one package per choice and creates its
sandboxes from it; the kit cache keeps each composition apart.

The example creates the sandbox and reads both, without starting Claude Code:
no credential is used.

Run it with:

    just example agent-kit-args
"""

from __future__ import annotations

import json

import common
import fastsandbox
from common import kit

MODEL = "claude-haiku-5-5"
"""The model chosen for the sandbox."""

EFFORT = "low"
"""The effort chosen for the sandbox."""

SETTINGS = "/home/agent/.claude/settings.json"
"""The settings of Claude Code in the sandbox, written by the install command of the kit."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    # Kit arguments are part of the composition: this package is forged and
    # kept apart from the plain `claude` kit.
    package = await kit.package(client, "claude", args={"model": MODEL, "reasoningEffort": EFFORT})
    async with (
        client.create(fastsandbox.unique_name("example-kit-args"), kit=package) as sandbox,
        sandbox.running(),
    ):
        output = await sandbox.exec(
            ["printenv", "CLAUDE_MODEL", "CLAUDE_REASONING_EFFORT"], check=True
        )
        env = output.stdout.splitlines()
        if env != [MODEL, EFFORT]:
            raise common.ExampleError(f"unexpected environment: {env}")
        print(f"environment of the sandbox: CLAUDE_MODEL={MODEL}, CLAUDE_REASONING_EFFORT={EFFORT}")

        settings = json.loads(await sandbox.read_file(SETTINGS))
        if settings.get("model") != MODEL or settings.get("effortLevel") != EFFORT:
            raise common.ExampleError(
                f"unexpected settings: model {settings.get('model')!r}, "
                f"effortLevel {settings.get('effortLevel')!r}"
            )
        print(f"~/.claude/settings.json: model {MODEL}, effortLevel {EFFORT}")


if __name__ == "__main__":
    common.main(main)

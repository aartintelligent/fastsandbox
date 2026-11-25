"""probe: what a throw-away sandbox of Docker Sandboxes runs.

Docker Sandboxes must be installed and running for the current user (`sbx
version` answers):

    python probe.py
"""

from pydantic import BaseModel

import fastsandbox
from fastsandbox import Client


class Probe(BaseModel):
    """What a sandbox reports about itself."""

    system: str
    python: str


async def probe(client: Client, kit: str = "shell") -> Probe:
    """Creates a sandbox of `kit`, asks it for its system and Python, and deletes it."""
    # `create` deletes the sandbox when the block ends; `running()` holds a
    # session, without which the sandbox stops.
    async with client.create(kit=kit) as sandbox, sandbox.running():
        system = await sandbox.exec("uname -sm", timeout=30, check=True)
        python = await sandbox.exec(["python3", "--version"], timeout=30, check=True)
    return Probe(system=system.stdout.strip(), python=python.stdout.strip())


async def main() -> None:
    """Connects to the daemon of the current user and probes a `shell` sandbox."""
    client = await fastsandbox.connect()
    print((await probe(client)).model_dump_json(indent=2))


if __name__ == "__main__":
    fastsandbox.run(main())

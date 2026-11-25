"""Files in and out of a shell sandbox, from one file to whole directories.

The example writes a configuration file and an executable script, copies whole
directories in both directions, and moves tar archives as they are, for a
program that stores or streams them itself.

Run it with:

    just example shell-files
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import common
import fastsandbox
from common import kit

SUM_SCRIPT = """#!/bin/sh
awk '{ s += $1 } END { print s }' "$1" > /tmp/project/result.txt
"""
"""A script that sums the numbers of a file into `/tmp/project/result.txt`."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    # A small project on the host, copied into the sandbox below.
    host = make_project()
    project = host / "project"
    try:
        async with (
            client.create(fastsandbox.unique_name("example-files"), kit=package) as sandbox,
            sandbox.running(),
        ):
            # A single file, then an executable script.
            await sandbox.write_file("/tmp/settings.toml", 'level = "debug"\n')
            settings = await sandbox.read_text("/tmp/settings.toml")
            print(f"settings.toml: {settings}", end="")
            await sandbox.write_file("/tmp/sum.sh", SUM_SCRIPT, mode=0o755)

            # The host directory lands under its own name: /tmp/project.
            await sandbox.upload_dir(project, "/tmp")
            await sandbox.exec(["/tmp/sum.sh", "/tmp/project/src/data.txt"], check=True)

            # And comes back, results included, under ./back/project.
            await sandbox.download_dir("/tmp/project", host / "back")
            result = read_text(host / "back" / "project" / "result.txt")
            print(f"sum computed in the sandbox: {result.strip()}")

            # The same directory as a tar archive, kept as bytes, then
            # extracted elsewhere: the directory must exist first.
            archive = await sandbox.download_archive("/tmp/project")
            await sandbox.exec(["mkdir", "-p", "/tmp/copy"], check=True)
            await sandbox.upload_archive("/tmp/copy", archive)
            copied = await sandbox.exec(["cat", "/tmp/copy/project/result.txt"], check=True)
            print(
                f"archive of {len(archive)} bytes extracted again: "
                f"result.txt reads {copied.stdout.strip()}"
            )
    finally:
        shutil.rmtree(host, ignore_errors=True)


def make_project() -> Path:
    """Writes a small project under a new temporary directory of the host, and returns it.

    The directory holds `project/src/data.txt`, three numbers to sum.
    """
    host = Path(tempfile.mkdtemp(prefix="example-files-"))
    source = host / "project" / "src"
    source.mkdir(parents=True)
    (source / "data.txt").write_text("1\n2\n3\n")
    return host


def read_text(path: Path) -> str:
    """The contents of the file `path` of the host."""
    return path.read_text()


if __name__ == "__main__":
    common.main(main)

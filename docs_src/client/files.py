import sys
from pathlib import Path

import fastsandbox


async def main(project: Path) -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        # One file, then an executable script: the directory must exist.
        await sandbox.write_file("/tmp/settings.toml", 'level = "debug"\n')
        await sandbox.write_file("/tmp/check.sh", '#!/bin/sh\nls -R "$1"\n', mode=0o755)
        print(await sandbox.read_text("/tmp/settings.toml"), end="")

        # A directory lands under its own name: /work/<project.name>.
        await sandbox.exec(["mkdir", "-p", "/work"], check=True)
        await sandbox.upload_dir(project, "/work")
        await sandbox.exec(["/tmp/check.sh", f"/work/{project.name}"], check=True)

        # And comes back the same way, under results/<project.name>.
        await sandbox.download_dir(f"/work/{project.name}", project.parent / "results")


if __name__ == "__main__":
    fastsandbox.run(main(Path(sys.argv[1])))

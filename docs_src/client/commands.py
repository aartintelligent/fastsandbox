import fastsandbox
from fastsandbox.exceptions import CommandFailedError


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        # A string runs with `sh -c`; a list is the program and its arguments.
        output = await sandbox.exec("echo hello from $(hostname)")
        print(f"exit code {output.exit_code}: {output.stdout}", end="")
        await sandbox.exec(["ls", "-la", "/tmp"], check=True)

        # As root, in a directory, with variables and a deadline of its own.
        await sandbox.exec(
            ["make", "test"],
            user="0",
            working_dir="/work",
            env={"CI": "1"},
            timeout=600,
        )

        # A non-zero exit code is an output, not an error...
        failed = await sandbox.exec("exit 3")
        print(f"ok: {failed.ok}, exit code {failed.exit_code}")
        # ...unless the command is checked.
        try:
            await sandbox.exec("exit 3", check=True)
        except CommandFailedError as error:
            print(f"checked: exit code {error.exit_code}, stderr {error.stderr!r}")


if __name__ == "__main__":
    fastsandbox.run(main())

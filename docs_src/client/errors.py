import fastsandbox
from fastsandbox.exceptions import ConflictError, NotFoundError, SandboxError


async def main() -> None:
    client = await fastsandbox.connect()
    try:
        await client.sandbox("docs-no-such-sandbox").inspect()
    except NotFoundError as error:
        print(f"not found: HTTP {error.status}, during {error.operation}")

    async with client.create("docs-errors", kit="shell"):
        try:
            await client.create("docs-errors", kit="shell")
        except ConflictError as error:
            print(f"conflict: HTTP {error.status}, transient {error.transient}")
        except SandboxError as error:
            print(f"another error of fastsandbox: {error}")


if __name__ == "__main__":
    fastsandbox.run(main())

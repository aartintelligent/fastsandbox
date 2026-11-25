import os

import fastsandbox
from fastsandbox.models import CredentialsUpdate, CustomSecret


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        # The sandbox sees the placeholder; the proxy sends the value to the
        # hosts of the secret only.
        secret = CustomSecret.new(
            ["api.example.com"],
            sentinel="example-placeholder",
            value=os.environ.get("EXAMPLE_TOKEN", "dummy-token"),
        )
        print(f"as a log prints it: {secret.value}")
        await sandbox.push_credentials(CredentialsUpdate().with_custom_secret(secret))

        # A credential of a service `sbx` knows, as `sbx secret set` gives it.
        await sandbox.push_service_secret("github", os.environ.get("GH_TOKEN", "dummy"))
        print(f"recorded: {sorted((await sandbox.inspect()).credential_sources)}")
        await sandbox.remove_service_secret("github")

        # An empty list removes every custom secret of the sandbox.
        await sandbox.push_credentials(CredentialsUpdate().without_custom_secrets())


if __name__ == "__main__":
    fastsandbox.run(main())

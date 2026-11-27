import fastsandbox
from fastsandbox import Kit, KitDescriptor, LifecycleStep, Mixin

configure = LifecycleStep(
    command="mkdir -p ~/.acme && echo 'endpoint: https://api.acme.example' > ~/.acme/config.yaml"
).as_user("agent")
descriptor = (
    KitDescriptor.mixin("Acme tools")
    .with_description("The configuration of the Acme API, and its host")
    .with_install(configure)
    .with_network_allow("api.acme.example:443")
)
# Checked by the rules of the forge as it is made.
acme = Mixin(reference="/kits/acme-tools", descriptor=descriptor)
KIT = Kit(base="shell", mixins=(acme,))


async def main() -> None:
    client = await fastsandbox.connect()
    package = await client.package(KIT)  # forged without the `sbx` CLI
    print(f"{KIT.label}: {', '.join(package.kit_refs[1:])}")
    async with client.create(kit=package) as sandbox, sandbox.running():
        # The install command of the mixin ran when the sandbox was created.
        config = await sandbox.exec("cat ~/.acme/config.yaml", user="agent", check=True)
        print(f"{sandbox.name}: {config.stdout.strip()}")


if __name__ == "__main__":
    fastsandbox.run(main())

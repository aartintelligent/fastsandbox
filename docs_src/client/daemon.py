import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    daemon = client.daemon
    health = await daemon.health()
    print(f"sbx {health.version}: healthy {health.is_healthy}")

    # The settings changed from their default, and where their value comes from.
    for setting in await daemon.settings():
        if setting.value != setting.default:
            print(f"{setting.key} = {setting.value} ({setting.source})")

    for target, level in (await daemon.log_levels()).items():
        print(f"log level of {target}: {level}")

    for summary in (await daemon.disk_usage()).summaries:
        print(f"{summary.resource_type}: {summary.size} bytes, {summary.reclaimable} reclaimable")


if __name__ == "__main__":
    fastsandbox.run(main())

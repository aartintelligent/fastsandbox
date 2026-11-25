# Events, prompts and streams

Full page: https://aartintelligent.github.io/fastsandbox/client/events/

## API

### `client.events` (`Events`)

| Call | Gives |
|---|---|
| `await subscribe() -> Stream[DaemonEvent]` | recent state replayed, then a `sync` event (`is_sync`), then live events |
| `await subscribe_live() -> Stream[DaemonEvent]` | live events only |

`DaemonEvent`: `id`, `event_type`, `action` (`created`, `started`, `stopped`,
`deleted`, `published`…), `timestamp`, `sandbox_name`, `sandbox_id`, `seq`,
`data`; `kind -> EventKind`, `is_sync`, `is_about(name)`.
`EventKind` (`from fastsandbox.models import EventKind`): `SYNC`,
`SANDBOX_LIFECYCLE`, `SANDBOX_PORTS`, `POLICY_NETWORK`, `OTHER`.

### `client.prompts` (`Prompts`)

| Call | What it does |
|---|---|
| `await subscribe() -> Stream[PromptEvent]` | pending prompts, a `synced` line (`is_synced`), then new prompts |
| `await respond(id, option_id)` | answers a prompt with one of its options; `NotFoundError` for an unknown prompt |

`PromptEvent`: `action`, `id`; every other field is kept in `model_extra`
(the shape of a prompt is not documented by the daemon).

### `Stream[T]`

The type of every daemon stream: events, prompts, creation progress
(`client.sandboxes.create_stream()`), pull progress
(`client.images.pull_stream()`).

| Use | Behavior |
|---|---|
| `async for item in stream` | reads items; an error while reading (a dropped connection…) is raised as a `SandboxError` |
| `await stream.aclose()` | stops it and closes its connection |
| `async with stream:` | closes it on exit |

## Example

```python
import asyncio

import fastsandbox
from fastsandbox.models import EventKind


async def main() -> None:
    client = await fastsandbox.connect()
    events = await client.events.subscribe_live()  # subscribe before acting

    async def watch() -> None:
        async for event in events:
            if event.kind is EventKind.SANDBOX_LIFECYCLE:
                print(event.action, event.sandbox_name)

    watcher = asyncio.create_task(watch())
    async with client.create(kit="shell"):
        await asyncio.sleep(1)
    await asyncio.sleep(1)
    watcher.cancel()
    await events.aclose()

    pending = []
    async with await client.prompts.subscribe() as prompts:
        async for prompt in prompts:
            if prompt.is_synced:
                break
            pending.append(prompt)
    print(f"{len(pending)} prompts pending")


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- The event stream never ends on its own: read it in a task, and close it.
- Subscribe before the actions to follow, or use `subscribe()` and wait for
  the `sync` event to build a view of the current sandboxes first.
- `async with await client.events.subscribe() as events:`: the subscription is
  awaited first, then used as a context manager.
- A stream used after it was closed raises `RuntimeError`.
- A connection a rule denies is refused without a prompt; prompts are raised
  only when no rule decides.
- The fake daemon does not serve the event or prompt routes: a test adds them
  with `daemon.route()` or runs against the real daemon.

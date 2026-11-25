# Events and prompts

The daemon publishes what happens to its sandboxes as an event stream, and
the requests that wait for a human decision as a prompt stream. This page
covers both, and the [`Stream`][fastsandbox.Stream] they are read through.

## Events

```python title="docs_src/client/events.py"
--8<-- "docs_src/client/events.py"
```

[`client.events`][fastsandbox.Events] subscribes in one of two ways:

- [`subscribe()`][fastsandbox.Events.subscribe] first replays recent state,
  ends the replay with a `sync` event
  ([`is_sync`][fastsandbox.models.DaemonEvent.is_sync]), then sends the live
  events: what a program needs to build its view of the sandboxes, then keep
  it up to date;
- [`subscribe_live()`][fastsandbox.Events.subscribe_live] sends the live
  events only.

Subscribe before the actions to follow: the example above subscribes, then
creates a sandbox, and sees its creation.

A [`DaemonEvent`][fastsandbox.models.DaemonEvent] has an `event_type`, an
`action` (`created`, `started`, `stopped`, `deleted`, `published`…), the
`sandbox_name` it is about ([`is_about(name)`][fastsandbox.models.DaemonEvent.is_about])
and its `data`. [`kind`][fastsandbox.models.DaemonEvent.kind] sorts it into an
[`EventKind`][fastsandbox.models.EventKind]:

| Kind | Events |
|---|---|
| `SYNC` | the end of the replay |
| `SANDBOX_LIFECYCLE` | sandboxes created, started, stopped, deleted |
| `SANDBOX_PORTS` | ports published and unpublished |
| `POLICY_NETWORK` | network activity |
| `OTHER` | any other family; `event_type` names it |

## Streams

The event stream never ends on its own. A [`Stream`][fastsandbox.Stream] is
read with `async for`; [`aclose()`][fastsandbox.Stream.aclose], or leaving its
`async with` block, closes its connection to the daemon. An error while
reading, a dropped connection for instance, is raised by the iteration, as a
[`SandboxError`][fastsandbox.exceptions.SandboxError].

The other streams of the daemon are read the same way: the progress of a
creation ([`create_stream()`](sandboxes.md#following-a-creation)) and of an
image pull ([`pull_stream()`](images.md#pulling)), and the prompts.

## Approval prompts

A prompt is a request a sandbox raises for a human decision.
[`client.prompts.subscribe()`][fastsandbox.Prompts.subscribe] gives the
pending prompts, then a `synced` line
([`is_synced`][fastsandbox.models.PromptEvent.is_synced]), then the new prompts
as they are raised; [`respond(id, option_id)`][fastsandbox.Prompts.respond]
answers one with the identifier of one of its options, and raises
[`NotFoundError`][fastsandbox.exceptions.NotFoundError] for an unknown prompt.

```python title="docs_src/client/prompts.py"
--8<-- "docs_src/client/prompts.py"
```

!!! note
    A connection a rule denies is refused by the proxy, without a prompt.
    Prompts are presumably raised when no rule decides, which the default
    `default-allow-all` rule of `sbx` never lets happen: the shape of a prompt
    has not been observed yet. A
    [`PromptEvent`][fastsandbox.models.PromptEvent] has its `action` and `id`,
    and keeps every other field as an extra field (`model_extra`).

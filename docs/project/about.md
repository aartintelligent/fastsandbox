# About

fastsandbox is an independent, open source Python package for
[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/), written in Python
and Rust and maintained by [Aurelien Andre](https://github.com/aartintelligent).

## The author

fastsandbox is designed, written and maintained by
**[Aurelien Andre](https://github.com/aartintelligent)**, who also maintains
[`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox), the Rust
client of the socket it is built on, and its audit of the API of the daemon,
version by version. Issues, change requests and pull requests are read and
reviewed by the author.

## The idea

Docker Sandboxes runs code, and coding agents, in throw-away microVMs, driven
by the `sbx` CLI and the `sandboxd` daemon behind it. Python programs that
want to use it deserve an API rather than a command line to parse: typed
payloads, errors to match on, streams to iterate, and a way to declare the
work that runs in a sandbox as a plain typed function. fastsandbox is that
API, from a client that reaches every route of the daemon to a framework that
gets a coding agent to work in a sandbox of its own in a few lines.

## Relationship with Docker

fastsandbox is not affiliated with, sponsored or endorsed by Docker, Inc. It
is a community project built on the `sandboxd` socket API, which is private
and changes with `sbx` releases; each release of fastsandbox states the range
of API versions it was checked against (see
[Compatibility](../overview/compatibility.md)). The Docker name belongs to
Docker, Inc. and appears on this site only to name the product the package
talks to.

Questions about Docker Sandboxes itself belong to the
[Docker documentation](https://docs.docker.com/ai/sandboxes/).

## Principles

- **One source of truth.** Everything about the daemon comes from
  `docker-sandbox` and its audit; the native extension only bridges it, and
  every helper, default and convenience is Python.
- **Typed, end to end.** Every payload is a Pydantic model, every public item
  is annotated and checked by mypy in strict mode, every error is a class.
- **Documented and tested.** Every public name is in the
  [reference](../reference/index.md), every snippet of this site is run by the
  test suite, and the coverage threshold only goes up.
- **Open by default.** MIT or Apache-2.0, developed in public, with a
  [contributing guide](contributing.md) you can follow.

## Links

- [Repository](https://github.com/aartintelligent/fastsandbox) and
  [issues](https://github.com/aartintelligent/fastsandbox/issues)
- [`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox), the
  Rust library underneath
- [fastsandbox on PyPI](https://pypi.org/project/fastsandbox/)
- [Releases](https://github.com/aartintelligent/fastsandbox/releases)
- [Aurelien Andre on GitHub](https://github.com/aartintelligent)

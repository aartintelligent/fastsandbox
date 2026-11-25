# Contributing

Contributions are welcome: bug reports, change requests, documentation and
pull requests. The repository's
[`CONTRIBUTING.md`](https://github.com/aartintelligent/fastsandbox/blob/main/CONTRIBUTING.md)
is the complete reference for tooling, development rules, quality gates and
commit conventions; this page is the short version.

## Bug reports

Open an [issue](https://github.com/aartintelligent/fastsandbox/issues/new/choose)
with the bug report template. The most useful report contains what you did,
what you expected and what happened instead, a small Python snippet that
reproduces it, and the versions: the output of `fastsandbox info`, which gives
those of `sbx` and of its API, with `python --version`. Remove any personal
data and secret first.

A failing test is even better: the test suite runs against a fake daemon that
serves the socket API in memory, so a reproduction is a few lines and needs no
sandbox (see [Testing](../guides/testing.md)).

Not every problem belongs here:

- a route or a field of the daemon that is missing belongs to
  [`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox/issues),
  the Rust library fastsandbox is built on;
- a problem of Docker Sandboxes itself, `sbx` or its daemon, belongs to
  Docker: see the [Docker documentation](https://docs.docker.com/ai/sandboxes/).

## Change requests

For a new capability or an API change, open a change request before writing
code. Say what you are trying to do with sandboxes rather than how you would
implement it; the design is discussed in the issue, then the pull request
follows it. A change that relies on a route of the daemon fastsandbox does not
reach yet starts in `docker-sandbox`.

## Documentation

This site and the docstrings it renders are part of the project. A typo, a
confusing sentence or a missing explanation is a valid pull request. The code
on the site is included from tested snippets, so a documentation change that
needs new code comes with the snippet and its test.

## Pull requests

1. Branch from `main`, and keep the change focused on one topic.
2. Run `uv sync`, then `just ci` locally; it runs the gates CI runs. A change
   to the calls to the daemon also runs `just test-live`, against the daemon
   of your user.
3. Write commits in the Conventional Commits format, since the changelog and
   the version numbers are generated from them.
4. Open the pull request with the template filled in, and wait for a review.

## Security vulnerabilities

Do not open a public issue for a security problem. Use GitHub's private
vulnerability reporting on the repository (*Security* tab, *Report a
vulnerability*). You will get an acknowledgement within 72 hours and a fix or
a mitigation plan within 14 days for confirmed issues; the
[security policy](security-policy.md) gives the details and the scope.

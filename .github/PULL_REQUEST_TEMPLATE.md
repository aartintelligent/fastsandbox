## Summary

<!-- What does this change and why? Link the issue it closes, e.g. "Closes #12". -->

## Checklist

- [ ] `just ci` passes locally (formatting, clippy, ruff, typos, mypy, tests, coverage, dependencies)
- [ ] Behaviour changes come with tests against the fake daemon; a new daemon route or field comes from `docker-sandbox` first
- [ ] `just test-live` passes when the change touches the calls to the daemon, and the touched examples run (`just example <name>`)
- [ ] Public API changes are documented (docstrings, README when user-facing) and called out above
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (see `CONTRIBUTING.md`)
- [ ] Breaking changes are marked with `!` in the commit type (e.g. `feat(client)!:`)

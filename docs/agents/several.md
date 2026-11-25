# Run several agents

Each run of a task has its own sandbox, so agents run side by side without
seeing each other's files, network rules or credentials. This page gives the
same issue to two agents, each on its own clone, and keeps the patch that
passes the tests.

```python title="docs_src/agents/several_agents.py" linenums="1" hl_lines="11 22-32 35 43 52-56"
--8<-- "docs_src/agents/several_agents.py"
```

- **Lines 22 to 32**: the work, written once: the agent of the task fixes the
  issue on its clone and commits, the tests decide, and the commits leave as a
  patch. `ctx.agent.name` says which agent did it.
- **Lines 35 and 43**: one task per agent, Claude Code and Codex, on the same
  inputs. A third agent is three more lines.
- **Line 11**: `max_concurrency=2` bounds how many runs of the application hold
  a sandbox at once; the others wait for a free slot before they create
  theirs.
- **Lines 52 to 56**: `async with app:` starts the application once, so that
  the runs share one client; `asyncio.gather` runs both tasks at once, and
  returns their results in order.

Run it with the key of each agent in the environment:

```console
$ export ANTHROPIC_API_KEY=sk-ant-... OPENAI_API_KEY=sk-...
$ python docs_src/agents/several_agents.py . "the parser drops the last line"
claude: passed
codex: failed
```

## Many runs of one agent

The same pattern runs one agent on many inputs, a review of each repository of
a list for instance:
`await asyncio.gather(*(review(repo=repo) for repo in repos))`. Each run gets
its own sandbox and its own clone; `max_concurrency` on the application, or on
the task with `@app.agent(..., max_concurrency=4)`, keeps the machine from
running them all at once.

## When one fails

`asyncio.gather` raises the first error of a run, and the other runs go on
until they end. With `return_exceptions=True`, it returns the errors in place
of the results instead, so that one failed agent does not hide the work of the
others. Whatever happens, each sandbox is deleted at the end of its run (see
[Running tasks](../framework/running.md#errors)).

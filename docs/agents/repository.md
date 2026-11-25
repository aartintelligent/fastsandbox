# Give it a repository

An agent works on files. How they get into its sandbox decides what it can
break, and how its work comes back to you. This page helps you choose, then
shows the three usual ways to get the work back: the tests decide, a patch, or
a file.

## Choose how it gets the code

The input that receives the directory carries a marker, in `Annotated`, that
says what happens to it:

| You want | Marker | The agent works on | Its changes |
|---|---|---|---|
| Changes to review before they land | `WorkspaceDir(clone=True)` | A private Git clone, at the same path | Stay in the sandbox; they leave as the result of the task |
| Changes made on your machine as it goes | `WorkspaceDir()` | Your directory, mounted read-write | Reach your files during the run |
| A copy to experiment on | `Uploaded("/work")` | A copy of the contents, under `/work` | Stay in the sandbox |
| Material to read, not to change | `Mounted("/data", read_only=True)` | Your directory, read-only, at `/data` | None |

**Start with the clone.** The agent may change and commit anything, your
repository stays as it is, and what you keep is what the task returns. Move to
the workspace once you trust the agent on a project and want its edits live.

!!! warning "The workspace is your directory"
    With `WorkspaceDir()`, the agent edits the files of your machine while it
    runs, and an interrupted run leaves its edits half done. Commit or stash
    your work before a run.

The markers, and what they do with paths, are detailed on
[Host paths](../framework/host-paths.md).

## Let the tests decide

What an agent reports about its work is not a result. Run the checks of the
project in the sandbox after it, and return what they say:

```python title="docs_src/agents/fix_bug.py" hl_lines="24 26 27"
--8<-- "docs_src/agents/fix_bug.py"
```

- **Line 24**: the prompt names the issue and the command that checks the fix.
- **Line 26**: the task runs that command itself, in the same sandbox, once
  the agent is done.
- **Line 27**: the exit code and the end of the output make the result, which
  Pydantic validates.

```sh
fastsandbox run docs_src/agents/fix_bug.py fix_bug --repo . --issue "the parser drops the last line"
```

## Get a patch

On a clone, the commits of the agent go with the sandbox. Have it commit, then
return its commits as a patch:

```python title="docs_src/agents/propose_patch.py" hl_lines="11 15 16 18-22"
--8<-- "docs_src/agents/propose_patch.py"
```

- **Line 15**: the commit the clone starts from, before the agent runs.
- **Line 16**: the prompt asks the agent to commit its fix.
- **Lines 18 to 22**: `git format-patch` turns the new commits into a patch,
  which the task returns as text.

The command line prints a string result as it is, so the patch goes straight
to a file, to read and apply with `git am`:

```sh
fastsandbox run docs_src/agents/propose_patch.py propose_patch --repo . --issue "the parser drops the last line" > fix.patch
git am fix.patch
```

## Get a file

For an answer rather than a change, ask the agent to write it to a file, and
read the file back, as the [quickstart](../get-started/quickstart.md) does:
`await ctx.sandbox.read_text(f"{workdir}/EXPLAINED.md")`. A file works the same
for every agent, whatever its output looks like. A whole directory comes back
with [`ctx.sandbox.download_dir(path, host_dir)`][fastsandbox.Sandbox.download_dir].

## Write a prompt you can check

The agent runs unattended: it cannot ask what you meant. A prompt that leads to
a run you can check says:

- **what to do**, with the issue, the error or the file it is about;
- **how to check it**, with the command that runs the tests;
- **what to leave behind**: commits on the clone, a file at a given path.

Then check it yourself, as the task does, rather than trusting the answer.

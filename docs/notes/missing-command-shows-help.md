## Missing Subcommand Should Show Help

**Priority:** Low
**Discovered:** 2026-03-16, during website brainstorming session

### Problem

Running a command group without a subcommand (e.g., `trinops config`, `trinops schema`, `trinops auth`) shows a terse "Missing command" error from Typer. This is unfriendly; it should show the `--help` output for that level instead.

### Proposed Solution

Add a `callback` to each Typer command group that invokes help when no subcommand is provided. Typer supports this via `invoke_without_command=True` on the group, then checking `ctx.invoked_subcommand is None` in the callback to print help.

### Affected Files

- `src/trinops/cli/commands.py` — `config_app`, `schema_app`, `auth_app` group definitions
- `src/trinops/cli/__init__.py` — top-level `app` if applicable

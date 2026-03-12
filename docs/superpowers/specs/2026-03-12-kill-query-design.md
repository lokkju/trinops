# Kill Query Support

## Summary

Add the ability to kill running queries from CLI and TUI. Uses `DELETE /v1/query/{id}` on the REST API. Gated by two config settings: `allow_kill` (feature toggle) and `confirm_kill` (confirmation UX).

## Config

Two new fields on `ConnectionProfile`:

- `allow_kill: bool = True` — controls whether kill is available at all; set `false` in locked-down environments
- `confirm_kill: bool = True` — controls whether a confirmation prompt is shown before killing

Both are persisted in `config.toml` and settable via `trinops config set`.

## Backend

`HttpQueryBackend.kill_query(query_id: str) -> bool`:
- Sends `DELETE /v1/query/{id}`
- Returns `True` on 204 (success) or 200
- Returns `False` on 404/410 (query already gone)
- Raises on other HTTP errors (auth failures, server errors)
- Handles both urllib and requests.Session code paths

`TrinopsClient.kill_query(query_id: str) -> bool`:
- Delegates to `HttpQueryBackend.kill_query` if HTTP backend
- Raises `NotImplementedError` for `SqlQueryBackend`

## CLI

Add `--kill` flag to the existing `query` command:

```
trinops query <id> --kill [--yes]
```

Behavior:
1. If `allow_kill` is false on the profile, print error and exit 1
2. Fetch query info (for confirmation display)
3. If `confirm_kill` is true and `--yes` not passed, prompt: `Kill query {id} by {user}? [{truncated_sql}] [y/N]`
4. Send kill request
5. Print result: "Query {id} killed" or "Query {id} not found (already completed?)"

## TUI

Keybinding `k` on a selected query row.

Behavior:
1. If `allow_kill` is false, the binding is not registered (not shown in footer)
2. On press, find the selected `QueryInfo`
3. If `confirm_kill` is true, show a Textual `Screen`-based confirmation dialog: "Kill query {id} by {user}?\n{truncated_sql}" with Yes/No buttons
4. On confirm, call `kill_query` in a worker thread
5. On success, trigger a refresh; on failure, show brief error in status bar

The kill binding is conditionally added in `on_mount` based on the profile's `allow_kill` setting, keeping it out of the footer entirely when disabled.

## Error Handling

- Auth failures (401/403) propagate as exceptions
- Network errors propagate as exceptions
- 404/410 are not errors; query is already gone
- SQL backend raises `NotImplementedError` with a clear message

## Testing

- Unit test for `HttpQueryBackend.kill_query` — mock server returning 204, 404, 410
- Unit test for `TrinopsClient.kill_query` with SQL backend (expect `NotImplementedError`)
- Unit test for config parsing of `allow_kill` and `confirm_kill` fields
- Mock DELETE handler in the existing `FakeTrinoAPI` test server

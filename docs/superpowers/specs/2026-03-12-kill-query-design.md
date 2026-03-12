# Kill Query Support

## Summary

Add the ability to kill running queries from CLI and TUI. Uses `DELETE /v1/query/{id}` on the REST API. Gated by two config settings: `allow_kill` (feature toggle) and `confirm_kill` (confirmation UX).

## Config

Two new fields on `ConnectionProfile`:

- `allow_kill: bool = True` — controls whether kill is available at all; set `false` in locked-down environments
- `confirm_kill: bool = True` — controls whether a confirmation prompt is shown before killing

Both are persisted in `config.toml` and settable via `trinops config set`.

### Prerequisite: bool coercion in `config set`

The `config_set` command currently only coerces `int` types. A `bool` branch must be added: `"true"/"1"` maps to `True`, `"false"/"0"` maps to `False`, anything else is rejected. This fix applies to all bool config fields, not just kill-related ones.

## Backend

### New private method: `HttpQueryBackend._delete(path: str) -> int`

A DELETE counterpart to `_get_json`, handling both the urllib and requests.Session code paths. Returns the HTTP status code. Follows the same dual-path pattern as the existing request infrastructure:

- urllib path: `Request(url, method="DELETE", headers=self._headers)` with `urlopen`
- requests.Session path: `self._session.delete(url, timeout=30)`

### `HttpQueryBackend.kill_query(query_id: str) -> bool`

Calls `self._delete(f"/v1/query/{query_id}")`:
- Returns `True` on 204 or 200
- Returns `False` on 404/410 (query already gone)
- Raises on other HTTP errors (auth failures, server errors)
- Error handling mirrors `get_query_raw`: catches `HTTPError`/`requests.HTTPError` with status code checks

`kill_query` is NOT added to the `QueryBackend` Protocol. `TrinopsClient.kill_query()` uses `hasattr` to check for the method, matching the existing pattern used by `get_query_raw` (client.py line 46).

### `TrinopsClient.kill_query(query_id: str) -> bool`

- If backend has `kill_query`, delegates to it
- Otherwise raises `NotImplementedError("kill_query requires HTTP backend")`

## CLI

New top-level command `trinops kill`:

```
trinops kill <query_id> [--yes]
```

Using a separate command rather than `--kill` on `query`, since kill is a different action than display.

Behavior:
1. Build profile; check `allow_kill` — if false, print error and exit 1
2. Check backend is HTTP — if SQL, print error and exit 1
3. Fetch query info via `get_query` for confirmation display
4. If `confirm_kill` is true and `--yes` not passed, prompt: `Kill query {id} by {user}? [{truncated_sql(80)}] [y/N]`
5. Send kill request
6. Print result: "Query {id} killed" or "Query {id} not found (already completed?)"

The `--yes` flag skips confirmation regardless of `confirm_kill` setting.

## TUI

Keybinding `k` on a selected query row.

The binding is always registered with `show=allow_kill` so it appears in the footer only when enabled. The `action_kill_query` method guards on `allow_kill` before acting, so even if triggered programmatically when disabled, it no-ops.

Behavior when enabled:
1. Find the selected `QueryInfo` from the cursor row
2. If `confirm_kill` is true, push a Textual confirmation `Screen`: "Kill query {id} by {user}?\n{truncated_sql(80)}" with Yes/No buttons
3. On confirm (or immediately if `confirm_kill` is false), call `kill_query` in a worker thread
4. On success, flash "Killed {id}" in status bar, trigger a refresh
5. On failure (query gone), flash "Query {id} already completed" in status bar
6. On error, flash error message in status bar

## Error Handling

- Auth failures (401/403) propagate as exceptions
- Network errors propagate as exceptions
- 404/410 are not errors; query is already gone
- SQL backend raises `NotImplementedError` with a clear message

## Testing

- Unit test for `HttpQueryBackend.kill_query` — mock server returning 204, 404, 410
- Unit test for bool coercion in `config_set`
- Unit test for `TrinopsClient.kill_query` with SQL backend (expect `NotImplementedError`)
- Unit test for config parsing of `allow_kill` and `confirm_kill` fields
- Mock DELETE handler in the existing `FakeTrinoAPI` test server

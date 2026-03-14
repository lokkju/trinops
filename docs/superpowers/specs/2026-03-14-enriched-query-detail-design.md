# Enriched Query Detail in TUI

**GitHub Issue:** #2

**Goal:** Replace the TUI's flat detail pane with a tabbed view that surfaces the full REST API response data in an organized, navigable layout.

**Architecture:** Dedicated Textual widget per tab, hosted in a `TabbedContent` container within a `DetailPane` wrapper. Each tab receives the raw `/v1/query/{id}` REST response dict and renders its slice of the data. The detail pane fetches via `get_query_raw()` (already exists on `TrinopsClient`).

## Navigation Model

Selecting a query row in the table opens the detail view and captures keyboard focus. Tab/Shift+Tab cycles through detail tabs. Escape closes the detail view and returns focus to the query list. Arrow keys within the detail view scroll the active tab's content rather than moving through the query list.

This replaces the current behavior where Tab/Shift+Tab moves focus between the query table and the detail pane. The detail view becomes a focused mode: you enter it by selecting a row, navigate within it using Tab, and leave with Escape.

The kill query keybinding (`k`) should remain active while the detail view is focused, operating on the currently displayed query. The `DetailPane` tracks the `query_id` of the currently displayed query; `action_kill_query` reads from the detail pane when it is focused, falling back to the table cursor otherwise. This avoids stale references if the query list refreshes and reorders while the detail view is open.

## Tabs

### Overview (default)

The current detail pane content, reorganized for the wider layout. Metadata fields in columns where terminal width permits (left: query ID, state, user, source; right: catalog, schema, created, elapsed, CPU, memory). Full SQL text below a separator, syntax-highlighted using Rich's `Syntax` renderable (which supports SQL).

Data sources: `queryId`, `state`, `session.user`, `session.source`, `session.catalog`, `session.schema`, `queryStats.createTime`, `queryStats.elapsedTime`, `queryStats.totalCpuTime`, `queryStats.peakUserMemoryReservation`, `query`. Session fields like `catalog` and `schema` may be absent; display "—" or omit the field when null.

### Stats

Detailed numeric breakdown from `queryStats`. Multi-column layout using available terminal width.

Timing section: queued, planning, execution, elapsed, total CPU. All parsed from Trino's Airlift duration format (already supported by `formatting.parse_duration_millis`).

Data section: physical input size and rows, processed input size and rows, output size and rows, spilled data size. Sizes parsed from Airlift data size format (already supported by `formatting.parse_data_size_bytes`).

Memory section: peak user memory, peak total memory, cumulative user memory.

Tasks section: completed tasks / total tasks, completed drivers / total drivers.

Data sources: all fields within `queryStats`.

### Tables

Accessed tables parsed from the `inputs` array in the REST response. Each table shown as `catalog.schema.table` with its columns listed in a table (column name, data type). The `inputs` array is only present in the full `/v1/query/{id}` response, not in the list response.

When `inputs` is absent or empty, shows "No table information available."

Data sources: `inputs[].catalogName`, `inputs[].schema`, `inputs[].table`, `inputs[].columns[].name`, `inputs[].columns[].type`.

### Errors

Error code, error type, and error name from `errorCode` (which is an object with `code`, `name`, `type` fields). Failure message from `failureInfo.message`. Warnings from the `warnings` array.

When the query has no errors or warnings, shows "No errors or warnings."

Data sources: `errorCode`, `failureInfo.message`, `warnings`.

## Code Structure

New and modified files:

- `src/trinops/tui/detail.py` (new) — `DetailPane` widget. Contains `TabbedContent` with the four tab widgets. Exposes `update(data: dict)` to receive raw REST response. Handles tab cycling and focus management.
- `src/trinops/tui/tabs/__init__.py` (new)
- `src/trinops/tui/tabs/overview.py` (new) — `OverviewTab` widget
- `src/trinops/tui/tabs/stats.py` (new) — `StatsTab` widget
- `src/trinops/tui/tabs/tables.py` (new) — `TablesTab` widget
- `src/trinops/tui/tabs/errors.py` (new) — `ErrorsTab` widget
- `src/trinops/tui/app.py` (modify) — Replace inline detail pane rendering with `DetailPane` widget. Change `_show_detail()` to call `get_query_raw()` and pass the dict to `DetailPane.update()`. Update keybindings for the new navigation model.

## Data Flow

1. User selects a query row in the table.
2. `app.py` spawns a worker calling `client.get_query_raw(query_id)`.
3. If the response is `None` (query purged, HTTP 404/410), the detail pane shows "Query no longer available" and does not switch to the detail view.
4. On success, the raw dict is passed to `detail_pane.update(data)`.
5. `DetailPane` stores the `query_id` and distributes the dict to each tab widget.
6. Each tab parses and renders its slice of the data.
7. Focus transfers to the detail pane; Tab/Shift+Tab cycles tabs.
8. Escape closes the detail pane and returns focus to the query table.

## Future Tabs (out of scope)

Issue #5 covers Stages and Plan tabs, which require recursive parsing of the `outputStage` tree. The tab infrastructure built here will accommodate them — adding a tab means creating a new widget file and registering it in `DetailPane`.

## Layout

The current detail pane CSS uses `max-height: 50%` and `display: none` toggling. The new `DetailPane` replaces this CSS. The tabbed content needs adequate vertical space; `max-height: 50%` is a reasonable starting point but should be tested with the Stats tab (which has the most content) and adjusted if needed. The detail pane should use Textual's `TabbedContent` widget, which handles tab header rendering and content switching natively.

## Testing

- Unit tests for each tab widget: given a raw REST response dict, verify the rendered content contains expected values.
- Unit tests for `DetailPane`: verify tab cycling, update propagation, empty/error states, and `None` response handling.
- Integration test: verify the navigation model (detail opens on selection, Tab cycles, Escape closes).
- New comprehensive REST response fixtures are needed; the existing `BASIC_QUERY_INFO` in `test_http_backend.py` lacks `inputs`, `failureInfo`, `warnings`, detailed `session` fields, and many `queryStats` fields that the new tabs require. Create a `FULL_QUERY_INFO` fixture with all fields populated and a `FAILED_QUERY_INFO` fixture with error data.

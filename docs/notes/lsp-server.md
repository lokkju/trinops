## LSP Server for Trino SQL

**Priority:** Low (future)
**Discovered:** 2026-03-16, during website brainstorming session

### Problem

trinops already has local schema cache with table/column metadata. An LSP server could provide SQL autocompletion, go-to-definition for tables, and inline diagnostics for Trino SQL in any editor.

### Context

This builds on the schema cache (`src/trinops/schema/`) and would be a new top-level module (`src/trinops/lsp/`). Would use `pygls` or similar Python LSP framework. Could be started via `trinops lsp` and configured in editors via standard LSP settings.

### Scope

- Autocomplete: catalog.schema.table names, column names within context
- Hover: show column types for table references
- Diagnostics: flag unknown tables/columns against cached schema

### Dependencies

- Schema cache must be populated first (`trinops schema refresh`)
- Needs a Python LSP framework (pygls)
- Editor integration docs for VS Code, Neovim, Emacs

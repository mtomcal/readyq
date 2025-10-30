# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

readyq is a single-file, dependency-free task tracking system inspired by Beads AI. The entire application lives in `readyq.py` (17KB) and uses only Python 3 standard library.

**Core constraint**: No external dependencies allowed. Everything must use Python standard library only.

## Development Commands

### Testing the CLI

```bash
# Basic workflow test
./readyq.py quickstart
./readyq.py new "Test task 1"
TASK1_ID=$(./readyq.py list | tail -1 | awk '{print $1}')
./readyq.py new "Test task 2" --blocked-by $TASK1_ID
./readyq.py list
./readyq.py ready  # Should show only task 1
./readyq.py update $TASK1_ID --status done
./readyq.py ready  # Should now show task 2 (unblocked)
```

### Testing the Web UI

```bash
./readyq.py web
# Opens browser to http://localhost:8000
# Manually test:
#   - Create task via "New Task" button
#   - Edit task via "Edit" link (test all fields)
#   - Add/delete session logs
#   - Start/Done/Re-open buttons
#   - Dependency graph updates
#   - Modal scrolling with long content
```

### Running Examples

```bash
chmod +x examples/*.sh
./examples/01-basic-usage.sh
./examples/02-dependencies.sh
./examples/03-ai-agent-workflow.sh
```

### Cleanup Between Tests

```bash
rm .readyq.jsonl
```

## Architecture

### Single-File Design

The entire application is in `readyq.py` (~1000 lines):
- Lines 1-36: Imports and configuration
- Lines 38-98: File locking implementation (cross-platform lock file pattern)
- Lines 100-137: Database layer (JSONL operations with locking)
- Lines 139-174: Helper functions
- Lines 176-266: CLI command handlers (quickstart, new, list, ready, update, show)
- Lines 267-422: `cmd_update()` with full edit capabilities (title, description, dependencies, session logs)
- Lines 424-733: Web UI server with modal forms and session log management
- Lines 735-893: HTTP handlers (GET and POST) with create/edit/delete-log endpoints
- Lines 895-986: Main CLI argument parser with extended flags

### Data Storage Strategy

**File**: `.readyq.jsonl` (JSONL = JSON Lines, one task per line)

**Task Schema**:
```json
{
  "id": "hex-uuid",
  "title": "string",
  "description": "string (detailed task context)",
  "status": "open|in_progress|blocked|done",
  "created_at": "ISO8601-UTC",
  "updated_at": "ISO8601-UTC",
  "blocks": ["task-id-1", "task-id-2"],
  "blocked_by": ["task-id-3"],
  "sessions": [
    {
      "timestamp": "ISO8601-UTC",
      "log": "string (what was learned/done)"
    }
  ]
}
```

**New in v0.1**: Added `description` and `sessions` fields for AI agent persistent memory.

**Critical Performance Trade-off**:
- `db_append_task()`: Fast append (new tasks only) with locking overhead (~50ms)
- `db_save_tasks()`: Rewrites entire file (used for updates affecting dependencies)
- File locking adds minimal overhead (<100ms for typical operations)
- Lock acquisition uses 50ms retry interval, 5-second timeout for queuing
- This design is acceptable for hundreds of tasks, not thousands

### Dependency Graph Management

The graph is maintained bidirectionally:

1. When creating task B blocked by task A:
   - A.blocks = [..., B.id]
   - B.blocked_by = [..., A.id]

2. When marking task A as done (readyq.py:209-226):
   - For each task in A.blocks:
     - Remove A.id from that task's blocked_by list
     - If blocked_by becomes empty, set status from 'blocked' to 'open'
   - This automatic unblocking is core functionality

3. The `ready` command (readyq.py:161-189):
   - Returns tasks where status != 'done' AND (blocked_by is empty OR all blockers are done)

### Web UI Architecture

The web server embeds a single-page HTML app with modal forms (readyq.py:444-733):

**Frontend (HTML/CSS/JavaScript)**:
- Inline CSS and JavaScript (no external files)
- Modal-based forms for create and edit operations
- Client-side logic determines "ready" state
- Session log display with delete buttons
- Scrollable modals with sticky headers

**API Endpoints**:
- `GET /`: Returns HTML with embedded CSS/JS
- `GET /api/tasks`: Returns JSON task list
- `GET /api/update?id=X&status=Y`: Quick status updates (legacy, for Start/Done/Re-open buttons)
- `POST /api/create`: Creates new task with all fields (title, description, blocked_by)
- `POST /api/edit`: Edits existing task with all fields (title, description, status, dependencies, logs)
- `POST /api/delete-log`: Deletes session log by index

**FakeArgs Pattern**: The web handlers create `FakeArgs` objects (CreateArgs, EditArgs) to reuse CLI logic. This means stdout/stderr from updates goes to server console, not HTTP response. This pattern maintains code reuse while keeping the single-file constraint.

## Key Implementation Details

### Task ID Resolution

`find_task()` (readyq.py:66-83) supports **partial ID matching**:
- User provides first few characters (e.g., "c4a0")
- Function finds unique match or reports ambiguity
- This makes CLI usage much faster than typing full UUIDs

### Concurrency Protection

**File locking implemented** (readyq.py:41-98). Uses lock file pattern (`.readyq.jsonl.lock`) for cross-platform compatibility.

**How it works**:
- `db_lock()` context manager acquires exclusive lock before any file operation
- Uses `os.open()` with `O_CREAT | O_EXCL` for atomic lock file creation
- 5-second timeout with 50ms retry interval for queuing behavior
- Automatic stale lock cleanup (locks older than 10 seconds)
- Lock file contains PID for debugging

**Protected operations**:
- `db_save_tasks()`: Rewrite entire file (used for updates/dependencies)
- `db_append_task()`: Append new task (technically atomic but locked for consistency)

**Performance**:
- Multiple processes can safely use readyq concurrently
- Operations queue up if lock is held (up to 5-second timeout)
- Typical lock hold time: <100ms for small databases (<1000 tasks)

**Error handling**:
- `TimeoutError` raised if lock can't be acquired within 5 seconds
- Suggests another process is using readyq or lock is stale
- Stale locks (>10s old) automatically removed and retried

### Web Server Threading

Uses `socketserver.ThreadingTCPServer` (readyq.py:383) to handle multiple browser requests concurrently. Without threading, clicking buttons rapidly would block.

## Adding New Features

### Adding a New CLI Command

1. Create handler function: `def cmd_yourcommand(args):`
2. Add subparser in `main()` (after line 409)
3. Set handler: `parser_yourcommand.set_defaults(func=cmd_yourcommand)`
4. Update README.md CLI Reference table
5. Test manually

### Modifying Task Schema

**Danger**: Changing schema breaks existing `.readyq.jsonl` files.

If you must:
1. Version the change (MAJOR semver bump)
2. Add migration script
3. Update CHANGELOG.md with migration instructions
4. Update examples in README.md

### Adding Web API Endpoints

**For GET endpoints**: Add `elif url.path == '/api/newendpoint':` in `WebUIHandler.do_GET()` (around line 735).

**For POST endpoints**: Add `elif url.path == '/api/newendpoint':` in `WebUIHandler.do_POST()` (around line 790).

**Pattern**: Use the FakeArgs pattern to reuse CLI logic. Create a custom args class with the needed attributes and call the appropriate `cmd_*()` function.

### SQLite Variant

CONTRIBUTING.md (lines 132-168) sketches an SQLite variant. If implementing:
- Add `--storage` flag (jsonl|sqlite)
- Keep JSONL as default for compatibility
- Abstract database layer behind interface

## Testing Checklist

Before committing changes:

**CLI Tests:**
- [ ] Run basic workflow test (see above)
- [ ] Test ambiguous ID prefix: create 2 tasks starting with 'a', update with prefix 'a'
- [ ] Test invalid blocker: `./readyq.py new "Task" --blocked-by nonexistent`
- [ ] Test empty database: `rm .readyq.jsonl && ./readyq.py list && ./readyq.py ready`
- [ ] Test dependency chain: A blocks B blocks C, mark A done, verify B unblocked
- [ ] Test `--add-blocks` and `--add-blocked-by` flags
- [ ] Test `--title` and `--description` update flags
- [ ] Test `--delete-log` with valid and invalid indices
- [ ] Test session log viewing with `./readyq.py show <id>`

**Web UI Tests:**
- [ ] Test `./readyq.py web` in browser
- [ ] Test creating tasks via "New Task" button
- [ ] Test editing all fields via "Edit" button
- [ ] Test adding dependencies through edit modal
- [ ] Test deleting session logs via web UI
- [ ] Test modal scrolling with long content/many logs
- [ ] Test Start/Done/Re-open buttons still work

**Concurrency Tests:**
- [ ] Test concurrent operations: `python3 test_race_conditions.py`
- [ ] Test lock timeout: `python3 test_lock_timeout.py`

## Common Pitfalls

1. **Don't add dependencies**: No `import requests`, no `pip install`. Only stdlib.

2. **Don't break JSONL format**: Each line must be valid JSON. The file must work with `jq`, `grep`, etc.

3. **Don't optimize prematurely**: The file rewrite on update is acceptable for the target use case (<1000 tasks).

4. **Don't forget bidirectional updates**: When modifying dependency graph, update both sides (blocks/blocked_by).

5. **Update logic reuse in web handler**: The `FakeArgs` pattern (readyq.py:360) is intentional. Don't refactor without understanding why the CLI logic is reused.

6. **Don't bypass db_lock()**: All file operations must use `db_lock()` context manager to prevent race conditions. Test concurrent operations with `test_race_conditions.py`.

## Design Principles (from CONTRIBUTING.md)

1. **Zero Dependencies**: Only Python 3 stdlib
2. **Single File**: Keep everything in readyq.py
3. **Simplicity**: Favor readability
4. **CLI-First**: Optimize for command-line use
5. **Git-Friendly**: Maintain JSONL format

## Completed Features

Recent additions:
- ✅ `show <id>` for detailed task view with session logs
- ✅ `--add-blocks` and `--add-blocked-by` for dependency editing
- ✅ `--title` and `--description` for updating task metadata
- ✅ `--delete-log` for removing session logs
- ✅ File locking for concurrency (lock file pattern)
- ✅ Web UI with create/edit modals
- ✅ Session log management in web UI
- ✅ Modal scrolling support

## Planned Features (from CONTRIBUTING.md)

High priority:
- `delete` command for removing tasks
- `search` with pattern matching
- `export` command (JSON, CSV, Markdown)
- Dependency removal (`--remove-blocks`, `--remove-blocked-by`)

Advanced:
- Terminal UI with curses
- SQLite storage option
- Git auto-commit integration
- Task templates
- Task tags/labels

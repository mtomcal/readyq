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
./readyq.py --web
# Opens browser to http://localhost:8000
# Manually test: Start/Done/Re-open buttons, dependency graph updates
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

The entire application is in `readyq.py`:
- Lines 1-33: Imports and configuration
- Lines 34-62: Database layer (JSONL operations)
- Lines 64-99: Helper functions
- Lines 101-231: CLI command handlers (quickstart, new, list, ready, update)
- Lines 233-376: Web UI server and HTTP handler
- Lines 378-446: Main CLI argument parser

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
- `db_append_task()`: Fast append (new tasks only)
- `db_save_tasks()`: Rewrites entire file (used for updates affecting dependencies)
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

The web server embeds a single-page HTML app (readyq.py:252-332):
- Inline CSS and JavaScript (no external files)
- Client-side logic determines "ready" state (lines 300-304)
- API endpoints:
  - `GET /`: Returns HTML
  - `GET /api/tasks`: Returns JSON task list
  - `GET /api/update?id=X&status=Y`: Updates task, redirects to /

**Hacky but works**: The web handler creates a `FakeArgs` object (readyq.py:360-363) to reuse CLI update logic. This means stdout/stderr from updates goes to server console, not HTTP response.

## Key Implementation Details

### Task ID Resolution

`find_task()` (readyq.py:66-83) supports **partial ID matching**:
- User provides first few characters (e.g., "c4a0")
- Function finds unique match or reports ambiguity
- This makes CLI usage much faster than typing full UUIDs

### Concurrency Warning

**No file locking**. Concurrent writes will corrupt `.readyq.jsonl`. Documented limitation. Future enhancement would add file locking with `fcntl` (Unix) or `msvcrt` (Windows).

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

Add `elif url.path == '/api/newendpoint':` in `WebUIHandler.do_GET()` (after line 348).

### SQLite Variant

CONTRIBUTING.md (lines 132-168) sketches an SQLite variant. If implementing:
- Add `--storage` flag (jsonl|sqlite)
- Keep JSONL as default for compatibility
- Abstract database layer behind interface

## Testing Checklist

Before committing changes:

- [ ] Run basic workflow test (see above)
- [ ] Test `./readyq.py --web` in browser
- [ ] Test ambiguous ID prefix: create 2 tasks starting with 'a', update with prefix 'a'
- [ ] Test invalid blocker: `./readyq.py new "Task" --blocked-by nonexistent`
- [ ] Test empty database: `rm .readyq.jsonl && ./readyq.py list && ./readyq.py ready`
- [ ] Test dependency chain: A blocks B blocks C, mark A done, verify B unblocked

## Common Pitfalls

1. **Don't add dependencies**: No `import requests`, no `pip install`. Only stdlib.

2. **Don't break JSONL format**: Each line must be valid JSON. The file must work with `jq`, `grep`, etc.

3. **Don't optimize prematurely**: The file rewrite on update is acceptable for the target use case (<1000 tasks).

4. **Don't forget bidirectional updates**: When modifying dependency graph, update both sides (blocks/blocked_by).

5. **Update logic reuse in web handler**: The `FakeArgs` pattern (readyq.py:360) is intentional. Don't refactor without understanding why the CLI logic is reused.

## Design Principles (from CONTRIBUTING.md)

1. **Zero Dependencies**: Only Python 3 stdlib
2. **Single File**: Keep everything in readyq.py
3. **Simplicity**: Favor readability
4. **CLI-First**: Optimize for command-line use
5. **Git-Friendly**: Maintain JSONL format

## Planned Features (from CONTRIBUTING.md)

High priority:
- `delete` command
- `search` with pattern matching
- `export` command (JSON, CSV, Markdown)
- `show <id>` for detailed task view
- `--add-blocks` for `update` command

Advanced:
- Terminal UI with curses
- File locking for concurrency
- SQLite storage option
- Git auto-commit integration

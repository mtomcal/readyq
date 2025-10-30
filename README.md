# readyq

A dependency-free, JSONL-based task tracker with dependency management and persistent session logging. Built specifically for AI agents to maintain context across multiple work sessions, track learnings, and manage complex workflows—all using only Python's standard library.

## Features

- **Zero Dependencies**: Built entirely with Python 3 standard library
- **Persistent Memory**: Log session context and learnings to each task
- **Graph-Based Dependencies**: Track task relationships and automatic unblocking
- **AI-First Design**: Simple CLI perfect for AI agent integration
- **Session Logging**: Append-only log of what was learned and done per task
- **Task Descriptions**: Full context and requirements for each task
- **Git-Friendly**: Human-readable JSONL storage for easy version control
- **Portable**: Single-file CLI tool that works anywhere Python runs
- **Web UI**: Built-in web interface for visual task management

## Quick Start

```bash
# Make executable
chmod +x readyq.py

# Initialize
./readyq.py quickstart

# Create tasks with descriptions
./readyq.py new "Implement authentication" --description "Add JWT-based auth to API endpoints"
./readyq.py new "Write API tests" --blocked-by <task-id>

# View ready tasks
./readyq.py ready

# Start working and log progress
./readyq.py update <task-id> --status in_progress --log "Started research on JWT libraries"
./readyq.py update <task-id> --log "Implemented middleware, added tests"

# View task details and session history
./readyq.py show <task-id>

# Mark complete
./readyq.py update <task-id> --status done

# Launch web UI
./readyq.py --web
```

## Installation

### Option 1: Direct Download
```bash
curl -O https://raw.githubusercontent.com/yourusername/readyq/main/readyq.py
chmod +x readyq.py
./readyq.py quickstart
```

### Option 2: Clone Repository
```bash
git clone https://github.com/yourusername/readyq.git
cd readyq
./readyq.py quickstart
```

### Option 3: Add to PATH
```bash
# Copy to a directory in your PATH
sudo cp readyq.py /usr/local/bin/readyq
sudo chmod +x /usr/local/bin/readyq

# Now use from anywhere
readyq quickstart
```

## Usage

### Initialize a New Task File

```bash
./readyq.py quickstart
```

This creates a `.readyq.jsonl` file in the current directory.

### Create Tasks

```bash
# Simple task
./readyq.py new "Implement user authentication"

# Task with dependencies
./readyq.py new "Write API tests" --blocked-by c4a0b12d
```

### List Tasks

```bash
# All tasks
./readyq.py list

# Only ready (unblocked) tasks
./readyq.py ready
```

### Update Tasks

```bash
# Mark task as in progress
./readyq.py update c4a0b12d --status in_progress

# Mark task as done (automatically unblocks dependent tasks)
./readyq.py update c4a0b12d --status done

# Reopen a completed task
./readyq.py update c4a0b12d --status open
```

### Web Interface

```bash
./readyq.py --web
```

Launches a web server at `http://localhost:8000` with a clean, modern interface for managing tasks.

## Task States

- **open**: Task is ready to be worked on
- **in_progress**: Task is actively being worked on
- **blocked**: Task is waiting for dependencies
- **done**: Task is completed

## CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| `quickstart` | Initialize `.readyq.jsonl` in current directory |
| `new <title>` | Create a new task |
| `list` | Show all tasks |
| `ready` | Show all unblocked tasks |
| `show <id>` | Show detailed task info with description and session logs |
| `update <id>` | Update a task's properties |
| `--web` | Launch web UI |

### Options

| Option | Command | Description |
|--------|---------|-------------|
| `--description <text>` | `new` | Set detailed task description |
| `--blocked-by <ids>` | `new` | Comma-separated list of blocking task IDs |
| `--status <status>` | `update` | Set task status (open, in_progress, done, blocked) |
| `--log <text>` | `update` | Add a session log entry to the task |

## File Format

Tasks are stored in `.readyq.jsonl` (JSON Lines format). Each line is a complete JSON object:

```json
{
  "id": "c4a0b12d3e8f9a015e1b2c3f4d5e6789",
  "title": "Implement authentication",
  "description": "Add JWT-based authentication to API endpoints",
  "status": "in_progress",
  "created_at": "2025-10-30T15:30:00.000000+00:00",
  "updated_at": "2025-10-30T16:45:00.000000+00:00",
  "blocks": ["5e1b2c3f4d5e6789c4a0b12d3e8f9a01"],
  "blocked_by": [],
  "sessions": [
    {
      "timestamp": "2025-10-30T15:30:00.000000+00:00",
      "log": "Started research on JWT libraries. PyJWT looks good."
    },
    {
      "timestamp": "2025-10-30T16:45:00.000000+00:00",
      "log": "Implemented basic middleware. Added tests. Need refresh token logic next."
    }
  ]
}
```

## Use Cases

### For AI Agents

Perfect for maintaining context across sessions:

```bash
# Session 1: Agent starts work
readyq new "Refactor authentication module" --description "Migrate from session-based to JWT. Maintain backwards compatibility."
readyq update <id> --status in_progress --log "Analyzed current auth flow. Found 3 endpoints using sessions."

# Session 2: Agent resumes (context preserved in logs)
readyq show <id>  # Reviews previous session's findings
readyq update <id> --log "Implemented JWT middleware. Migrated login endpoint. 2 endpoints remaining."

# Session 3: Complete work
readyq update <id> --log "Migrated all endpoints. Added tests. All passing."
readyq update <id> --status done

# Create dependent tasks
readyq new "Update API documentation" --blocked-by <id>
readyq ready  # Shows newly unblocked task
```

### For Personal Workflows
```bash
# Morning planning
readyq new "Review pull requests"
readyq new "Write weekly report"
readyq new "Deploy to production" --blocked-by <review-id>

# Check what's ready
readyq ready

# Track progress
readyq update <id> --status in_progress
```

### For Team Projects
```bash
# Initialize in project root
cd ~/projects/myapp
readyq quickstart

# Track feature work
readyq new "Design API endpoints"
readyq new "Implement backend" --blocked-by <design-id>
readyq new "Build frontend" --blocked-by <backend-id>

# Commit to version control
git add .readyq.jsonl
git commit -m "Update task graph"
```

## Architecture

### Why JSONL?

- **Human-Readable**: Easy to inspect and edit with any text editor
- **Git-Friendly**: Line-based format creates clean diffs
- **Append-Only**: New tasks are fast (no file rewrite)
- **Simple**: No external database required

### Performance Considerations

The JSONL implementation is optimized for simplicity and portability:

- **Read Operations**: Fast—loads entire file into memory
- **Append Operations**: Fast—appends single line to file
- **Update Operations**: Moderate—rewrites entire file (acceptable for hundreds of tasks)

For larger workloads (thousands of tasks), consider the SQLite variant (see `CONTRIBUTING.md`).

### Concurrency

This tool uses file-based storage without locking. For concurrent use:

- **Single User**: No issues
- **Multiple Processes**: Risk of write conflicts
- **Solution**: Use git for merging changes (like Beads AI)

## Comparison to Beads AI

| Feature | readyq | Beads AI |
|---------|--------|----------|
| Dependencies | None (stdlib only) | Requires npm, Node.js |
| Database | JSONL only | JSONL + SQLite |
| Language | Python 3 | JavaScript/TypeScript |
| Web UI | Built-in HTTP server | Separate implementation |
| Git Integration | Manual | Automatic |
| Performance | Good (<1000 tasks) | Excellent (any scale) |

## Limitations

1. **Concurrency**: No file locking—concurrent writes may conflict
2. **Scale**: Updates rewrite entire file—not ideal for 10,000+ tasks
3. **Features**: Subset of Beads AI functionality

For production use with large teams, consider:
- Using git for change management
- Upgrading to SQLite variant (see `CONTRIBUTING.md`)
- Using Beads AI directly

## Contributing

Contributions welcome! See `CONTRIBUTING.md` for guidelines.

Ideas for contributions:
- Add `delete` command
- Implement `--add-blocks` for manual dependency editing
- Create `export` command (CSV, JSON, etc.)
- Add `search` and `filter` capabilities
- Build TUI (text user interface)

## License

MIT License - see `LICENSE` file for details.

## Acknowledgments

Inspired by [Beads AI](https://github.com/beadai/bd) by the Beads team. This project demonstrates how their graph-based task tracking concept can be implemented with zero dependencies.

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/readyq/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/readyq/discussions)

---

Made with Python's standard library

# Contributing to readyq

Thank you for your interest in contributing to readyq! This document provides guidelines and information for contributors.

## Code of Conduct

Be respectful, inclusive, and professional. We're here to build useful tools together.

## How to Contribute

### Reporting Bugs

1. Check existing issues to avoid duplicates
2. Create a new issue with:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Python version and OS
   - Contents of `.readyq.jsonl` (if relevant)

### Suggesting Features

1. Open an issue describing:
   - The use case
   - Proposed solution
   - Alternative approaches considered
   - Impact on existing functionality

### Contributing Code

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature-name`
3. **Make your changes**
4. **Test thoroughly**
5. **Commit with clear messages**
6. **Push and create a pull request**

## Development Guidelines

### Design Principles

1. **Zero Dependencies**: Only use Python 3 standard library
2. **Single File**: Keep everything in `readyq.py` (except docs)
3. **Simplicity**: Favor readability over cleverness
4. **CLI-First**: Optimize for command-line use
5. **Git-Friendly**: Maintain JSONL format compatibility

### Code Style

- Follow PEP 8 Python style guide
- Use descriptive variable names
- Add docstrings to all functions
- Keep functions focused and small
- Comment complex logic

Example:
```python
def find_task(task_id_prefix):
    """Finds a task by a partial (or full) ID.

    Args:
        task_id_prefix: The beginning of the task ID to search for

    Returns:
        A tuple of (task_dict, all_tasks_list) or (None, all_tasks_list)
    """
    # Implementation...
```

### Testing

Before submitting a PR, test:

```bash
# Basic functionality
./readyq.py quickstart
./readyq.py new "Test task 1"
./readyq.py new "Test task 2" --blocked-by <id>
./readyq.py list
./readyq.py ready
./readyq.py update <id> --status done
./readyq.py ready

# Delete command
./readyq.py delete <id>

# Dependency removal
./readyq.py update <id> --remove-blocks <id2>
./readyq.py update <id> --remove-blocked-by <id3>

# Web interface
./readyq.py web
# Test all UI actions in browser (create, edit, delete)

# Edge cases
./readyq.py update nonexistent --status done
./readyq.py new "Task" --blocked-by invalid-id
./readyq.py delete nonexistent
```

### File Structure

```
readyq/
├── readyq.py           # Main script (all code here)
├── README.md           # User documentation
├── CONTRIBUTING.md     # This file
├── LICENSE             # MIT license
├── .gitignore          # Git ignore rules
└── examples/           # Example workflows
```

## Feature Ideas

### Completed Features

- [x] Add `delete` command for removing tasks
- [x] Create `show <id>` for detailed task view
- [x] Add `--add-blocks` and `--add-blocked-by` to `update` command
- [x] Add `--remove-blocks` and `--remove-blocked-by` to `update` command
- [x] Support task descriptions (multi-line)
- [x] Implement file locking for concurrency
- [x] Session logging for persistent memory
- [x] Web UI with create/edit/delete functionality

### High Priority

- [ ] Implement `search` with pattern matching
- [ ] Add `export` command (JSON, CSV, Markdown)
- [ ] Implement `filter` by status, date, or tags

### Medium Priority

- [ ] Add task tags/labels support
- [ ] Create `stats` command for analytics
- [ ] Add `archive` for completed tasks
- [ ] Bulk operations support

### Advanced Features

- [ ] Build terminal UI with `curses`
- [ ] Add git integration (auto-commit)
- [ ] Create SQLite variant for large datasets
- [ ] Add export to Gantt chart format
- [ ] Support multiple memory files
- [ ] Task templates

## SQLite Variant

For users with larger datasets (1000+ tasks), an SQLite variant would be more performant:

```python
import sqlite3

def db_init():
    conn = sqlite3.connect('.readyq.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dependencies (
            task_id TEXT,
            blocks_task_id TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id),
            FOREIGN KEY(blocks_task_id) REFERENCES tasks(id)
        )
    ''')
    conn.commit()
    return conn
```

This would:
- Eliminate full-file rewrites on updates
- Support concurrent access better
- Scale to tens of thousands of tasks
- Still use only standard library (`sqlite3`)

If there's interest, we can add this as an optional mode.

## Documentation

When adding features:

1. Update function docstrings
2. Add usage examples to README.md
3. Update CLI help text in `main()`
4. Add to this CONTRIBUTING.md if architectural

## Release Process

1. Update version in `readyq.py` (if we add versioning)
2. Update CHANGELOG.md
3. Create git tag: `git tag -a v1.0.0 -m "Release 1.0.0"`
4. Push tag: `git push origin v1.0.0`

## Questions?

Open a GitHub Discussion or issue. We're happy to help!

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to readyq!

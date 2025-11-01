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

## File Locking Patterns

readyq uses a lock file pattern for cross-platform file locking. Here are the locking patterns evaluated during development:

### Pattern 1: fcntl-based locking (Unix/Linux/Mac only)
```python
import fcntl
import os

@contextmanager
def fcntl_lock(file_path, timeout=5.0):
    """Advisory file locking using fcntl.flock()"""
    lock_file = open(file_path, 'a')
    start_time = time.time()

    try:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, IOError) as e:
                if e.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.time() - start_time >= timeout:
                    raise TimeoutError(f"Lock timeout after {timeout}s")
                time.sleep(0.05)

        yield lock_file
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
```

**Pros**: Simple, built into OS, automatic cleanup on process death
**Cons**: Unix-only, not portable to Windows

### Pattern 2: Lock file pattern (cross-platform) ✅ CHOSEN
```python
@contextmanager
def lockfile_lock(base_path, timeout=5.0):
    """Use separate .lock file with atomic creation (O_CREAT | O_EXCL)"""
    lock_path = base_path + '.lock'
    start_time = time.time()
    lock_acquired = False

    try:
        while True:
            try:
                # Atomic lock file creation
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                os.write(fd, f"{os.getpid()}\n".encode())  # PID for debugging
                os.close(fd)
                lock_acquired = True
                break
            except FileExistsError:
                # Check for stale locks
                if time.time() - start_time >= timeout:
                    try:
                        lock_age = time.time() - os.path.getmtime(lock_path)
                        if lock_age > timeout * 2:
                            os.remove(lock_path)  # Remove stale lock
                            continue
                    except (OSError, FileNotFoundError):
                        pass
                    raise TimeoutError(f"Lock timeout after {timeout}s")
                time.sleep(0.05)

        yield
    finally:
        if lock_acquired:
            try:
                os.remove(lock_path)
            except (OSError, FileNotFoundError):
                pass
```

**Pros**: Cross-platform (Windows/Unix/Mac), explicit PID tracking, stale lock detection
**Cons**: Requires manual cleanup, potential for stale locks
**Why chosen**: Best balance of portability and simplicity for readyq's use case

### Pattern 3: Atomic append (no lock needed)
```python
def atomic_append(file_path, content):
    """Single write() calls are atomic on most filesystems (<4KB)"""
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(content)  # Single write is atomic
```

**Used for**: `db_append_task()` - fast task creation
**Trade-off**: Safe for appends, but read-modify-write cycles (like `db_save_tasks()`) need explicit locking

### Pattern 4: Atomic replace (for full rewrites)
```python
def atomic_replace(file_path, content):
    """Atomic file replacement using rename()"""
    temp_path = file_path + '.tmp'

    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())  # Ensure written to disk

    os.replace(temp_path, file_path)  # Atomic on all platforms
```

**Could be used for**: `db_save_tasks()` combined with locking
**Trade-off**: More robust but requires temp file management

### Implementation Notes

readyq uses **Pattern 2 (lock file)** for `db_lock()` context manager:
- Lock file: `.readyq.jsonl.lock`
- Timeout: 5 seconds (configurable)
- Retry interval: 50ms
- Stale lock threshold: 10 seconds (2× timeout)
- PID stored in lock file for debugging

All operations that modify the database use `db_lock()`:
```python
with db_lock(timeout=5.0):
    # Read-modify-write operations protected here
    tasks = db_load_tasks()
    # ... modify tasks ...
    db_save_tasks(tasks)
```

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

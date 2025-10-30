#!/usr/bin/env python3

"""
readyq.py: A dependency-free, JSONL-based task tracker with dependency management
and persistent session logging. Built for AI agents and designed to maintain context
across multiple work sessions.

Usage:
  ./readyq.py quickstart                              - Initialize the .readyq.jsonl file
  ./readyq.py new "My task" [--description "..."]     - Add a new task
  ./readyq.py list                                    - List all tasks
  ./readyq.py ready                                   - List all unblocked, open tasks
  ./readyq.py show <id>                               - Show detailed task info with session logs
  ./readyq.py update <id> [--status STATUS]           - Update task status
  ./readyq.py update <id> --log "..."                 - Add session log entry
  ./readyq.py update <id> --delete-log <index>        - Delete a session log by index
  ./readyq.py update <id> --title "..." --description "..." - Update task metadata
  ./readyq.py update <id> --add-blocks <ids>          - Add tasks this task blocks
  ./readyq.py update <id> --add-blocked-by <ids>      - Add tasks that block this task
  ./readyq.py update <id> --remove-blocks <ids>       - Remove tasks this task blocks
  ./readyq.py update <id> --remove-blocked-by <ids>   - Remove tasks that block this task
  ./readyq.py delete <id>                             - Delete a task and clean up dependencies
  ./readyq.py web                                     - Run web UI on http://localhost:8000
"""

import sys
import os
import json
import argparse
import uuid
import datetime
import webbrowser
import http.server
import socketserver
import threading
import time
from contextlib import contextmanager
from urllib.parse import urlparse, parse_qs

# --- Configuration ---

DB_FILE = ".readyq.jsonl"
HOST = "localhost"
PORT = 8000

# --- File Locking ---

@contextmanager
def db_lock(timeout=5.0):
    """
    Acquire exclusive lock on database file using lock file pattern.

    This prevents race conditions when multiple processes (e.g., multiple AI agents)
    attempt to modify the .readyq.jsonl file simultaneously. Uses a .lock file
    for cross-platform compatibility.

    Args:
        timeout: Maximum time in seconds to wait for lock acquisition (default: 5.0)

    Raises:
        TimeoutError: If lock cannot be acquired within timeout period
    """
    lock_path = DB_FILE + '.lock'
    start_time = time.time()
    lock_acquired = False

    try:
        while True:
            try:
                # Atomic create with O_CREAT | O_EXCL - fails if file exists
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                os.write(fd, f"{os.getpid()}\n".encode())
                os.close(fd)
                lock_acquired = True
                break

            except FileExistsError:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    # Check for stale lock (older than 2x timeout)
                    try:
                        lock_age = time.time() - os.path.getmtime(lock_path)
                        if lock_age > timeout * 2:
                            # Remove stale lock and retry
                            os.remove(lock_path)
                            continue
                    except (OSError, FileNotFoundError):
                        pass

                    raise TimeoutError(
                        f"Could not acquire database lock after {timeout}s. "
                        "Another process may be using readyq."
                    )

                # Retry after short delay
                time.sleep(0.05)  # 50ms

        yield

    finally:
        if lock_acquired:
            try:
                os.remove(lock_path)
            except (OSError, FileNotFoundError):
                pass

# --- Database Core Functions (JSONL) ---

def db_load_tasks():
    """Loads all tasks from the JSONL file into a list of dicts."""
    if not os.path.exists(DB_FILE):
        return []
    tasks = []
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                tasks.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: Skipping malformed line in {DB_FILE}", file=sys.stderr)
    return tasks

def db_save_tasks(tasks):
    """
    Overwrites the entire JSONL file with the current list of tasks.
    This is necessary for 'update' operations that modify multiple tasks
    (e.g., adding a dependency).

    Uses file locking to prevent race conditions during concurrent access.
    """
    with db_lock():
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            for task in tasks:
                f.write(json.dumps(task) + '\n')

def db_append_task(task):
    """
    Appends a single new task to the JSONL file (for 'new' operations).

    Uses file locking to prevent race conditions during concurrent access.
    """
    with db_lock():
        with open(DB_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(task) + '\n')

# --- Helper Functions ---

def find_task(task_id_prefix):
    """Finds a task by a partial (or full) ID."""
    if not task_id_prefix:
        return None, []

    tasks = db_load_tasks()
    matches = [t for t in tasks if t['id'].startswith(task_id_prefix)]

    if len(matches) == 1:
        return matches[0], tasks
    elif len(matches) > 1:
        print(f"Error: Ambiguous ID prefix '{task_id_prefix}'. Matches:", file=sys.stderr)
        for t in matches:
            print(f"  - {t['id']}: {t['title']}", file=sys.stderr)
        return None, tasks
    else:
        print(f"Error: Task '{task_id_prefix}' not found.", file=sys.stderr)
        return None, tasks

def get_short_id(task_id):
    """Returns a shortened 8-char ID for display."""
    return task_id[:8]

def print_task_list(tasks):
    """Helper to pretty-print a list of tasks."""
    if not tasks:
        print("No tasks found.")
        return

    print(f"{'ID':<9} {'Status':<12} {'Blocked':<5} {'Title':<40}")
    print("-" * 70)
    for task in tasks:
        is_blocked = 'Yes' if task.get('blocked_by') else 'No'
        print(f"{get_short_id(task['id']):<9} {task['status']:<12} {is_blocked:<5} {task['title']:<40}")

# --- CLI Command Handlers ---

def cmd_quickstart(args):
    """'quickstart' command: Creates the DB file."""
    if os.path.exists(DB_FILE):
        print(f"'{DB_FILE}' already exists.")
    else:
        # Just create an empty file
        open(DB_FILE, 'w').close()
        print(f"Initialized empty readyq file at '{DB_FILE}'.")

def cmd_new(args):
    """'new' command: Adds a new task."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_task = {
        "id": uuid.uuid4().hex,
        "title": args.title,
        "description": args.description if args.description else "",
        "status": "open",  # open, in_progress, done, blocked
        "created_at": now,
        "updated_at": now,
        "blocks": [],
        "blocked_by": [],
        "sessions": []
    }

    # This part is complex: if --blocked-by is used, we must
    # rewrite the *entire* database to update the other tasks.
    if args.blocked_by:
        tasks = db_load_tasks()
        new_task['status'] = 'blocked'
        blocker_ids = [bid.strip() for bid in args.blocked_by.split(',')]

        for blocker_id_prefix in blocker_ids:
            blocker_task = next((t for t in tasks if t['id'].startswith(blocker_id_prefix)), None)
            if blocker_task:
                # Add to new task's blocked_by list
                new_task['blocked_by'].append(blocker_task['id'])
                # Add to blocker task's blocks list
                if 'blocks' not in blocker_task:
                    blocker_task['blocks'] = []
                blocker_task['blocks'].append(new_task['id'])
                blocker_task['updated_at'] = now
            else:
                print(f"Warning: Blocker task '{blocker_id_prefix}' not found. Ignoring.", file=sys.stderr)

        tasks.append(new_task)
        db_save_tasks(tasks)

    else:
        # Simple case: just append the new task
        db_append_task(new_task)

    print(f"Created new task: {get_short_id(new_task['id'])}")

def cmd_list(args):
    """'list' command: Shows all tasks."""
    tasks = db_load_tasks()
    # Sort by creation time
    tasks.sort(key=lambda t: t['created_at'])
    print_task_list(tasks)

def cmd_ready(args):
    """'ready' command: Shows unblocked, non-done tasks."""
    tasks = db_load_tasks()

    # Beads 'ready' means:
    # 1. Status is not 'done'
    # 2. 'blocked_by' list is empty OR all tasks in 'blocked_by' are 'done'

    all_task_ids = {t['id']: t for t in tasks}
    ready_tasks = []

    for task in tasks:
        if task['status'] == 'done':
            continue

        is_ready = True
        if task.get('blocked_by'):
            for blocker_id in task['blocked_by']:
                blocker_task = all_task_ids.get(blocker_id)
                # If blocker is missing or not done, task is not ready
                if not blocker_task or blocker_task['status'] != 'done':
                    is_ready = False
                    break

        if is_ready:
            ready_tasks.append(task)

    print(f"Found {len(ready_tasks)} ready tasks:")
    print_task_list(ready_tasks)

def cmd_update(args):
    """'update' command: Modifies an existing task."""
    task, tasks = find_task(args.id)
    if not task:
        return

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    task['updated_at'] = now
    updated = False

    # Update title if provided
    if hasattr(args, 'title') and args.title:
        task['title'] = args.title
        updated = True
        print(f"Updated title to '{task['title']}'")

    # Update description if provided
    if hasattr(args, 'description') and args.description is not None:
        task['description'] = args.description
        updated = True
        print(f"Updated description")

    # Delete session log if requested
    if hasattr(args, 'delete_log') and args.delete_log is not None:
        try:
            log_index = int(args.delete_log)
            if 'sessions' not in task or log_index < 0 or log_index >= len(task['sessions']):
                print(f"Error: Invalid log index {log_index}. Task has {len(task.get('sessions', []))} session logs.", file=sys.stderr)
                return
            task['sessions'].pop(log_index)
            updated = True
            print(f"Deleted session log #{log_index} from task {get_short_id(task['id'])}")
        except ValueError:
            print(f"Error: --delete-log requires a numeric index", file=sys.stderr)
            return

    # Add session log if provided
    if hasattr(args, 'log') and args.log:
        if 'sessions' not in task:
            task['sessions'] = []
        task['sessions'].append({
            "timestamp": now,
            "log": args.log
        })
        updated = True
        print(f"Added session log to task {get_short_id(task['id'])}")

    # Add blocks (tasks that this task blocks)
    if hasattr(args, 'add_blocks') and args.add_blocks:
        block_ids = [bid.strip() for bid in args.add_blocks.split(',')]
        all_task_ids = {t['id']: t for t in tasks}

        for block_id_prefix in block_ids:
            blocked_task = next((t for t in tasks if t['id'].startswith(block_id_prefix)), None)
            if blocked_task:
                # Add to current task's blocks list
                if 'blocks' not in task:
                    task['blocks'] = []
                if blocked_task['id'] not in task['blocks']:
                    task['blocks'].append(blocked_task['id'])

                # Add to blocked task's blocked_by list
                if 'blocked_by' not in blocked_task:
                    blocked_task['blocked_by'] = []
                if task['id'] not in blocked_task['blocked_by']:
                    blocked_task['blocked_by'].append(task['id'])
                    blocked_task['updated_at'] = now
                    if blocked_task['status'] not in ['done', 'blocked']:
                        blocked_task['status'] = 'blocked'

                updated = True
                print(f"Added block: {get_short_id(task['id'])} blocks {get_short_id(blocked_task['id'])}")
            else:
                print(f"Warning: Task '{block_id_prefix}' not found. Ignoring.", file=sys.stderr)

    # Add blocked_by (tasks that block this task)
    if hasattr(args, 'add_blocked_by') and args.add_blocked_by:
        blocker_ids = [bid.strip() for bid in args.add_blocked_by.split(',')]

        for blocker_id_prefix in blocker_ids:
            blocker_task = next((t for t in tasks if t['id'].startswith(blocker_id_prefix)), None)
            if blocker_task:
                # Add to current task's blocked_by list
                if 'blocked_by' not in task:
                    task['blocked_by'] = []
                if blocker_task['id'] not in task['blocked_by']:
                    task['blocked_by'].append(blocker_task['id'])
                    if task['status'] not in ['done', 'blocked']:
                        task['status'] = 'blocked'

                # Add to blocker task's blocks list
                if 'blocks' not in blocker_task:
                    blocker_task['blocks'] = []
                if task['id'] not in blocker_task['blocks']:
                    blocker_task['blocks'].append(task['id'])
                    blocker_task['updated_at'] = now

                updated = True
                print(f"Added blocker: {get_short_id(blocker_task['id'])} blocks {get_short_id(task['id'])}")
            else:
                print(f"Warning: Blocker task '{blocker_id_prefix}' not found. Ignoring.", file=sys.stderr)

    # Remove blocks (tasks that this task blocks)
    if hasattr(args, 'remove_blocks') and args.remove_blocks:
        block_ids = [bid.strip() for bid in args.remove_blocks.split(',')]

        for block_id_prefix in block_ids:
            blocked_task = next((t for t in tasks if t['id'].startswith(block_id_prefix)), None)
            if blocked_task:
                # Remove from current task's blocks list
                if 'blocks' in task and blocked_task['id'] in task['blocks']:
                    task['blocks'].remove(blocked_task['id'])

                # Remove from blocked task's blocked_by list
                if 'blocked_by' in blocked_task and task['id'] in blocked_task['blocked_by']:
                    blocked_task['blocked_by'].remove(task['id'])
                    blocked_task['updated_at'] = now
                    # If this was the only blocker, unblock the task
                    if not blocked_task['blocked_by'] and blocked_task['status'] == 'blocked':
                        blocked_task['status'] = 'open'
                        print(f"Task {get_short_id(blocked_task['id'])} is now unblocked.")

                updated = True
                print(f"Removed block: {get_short_id(task['id'])} no longer blocks {get_short_id(blocked_task['id'])}")
            else:
                print(f"Warning: Task '{block_id_prefix}' not found. Ignoring.", file=sys.stderr)

    # Remove blocked_by (tasks that block this task)
    if hasattr(args, 'remove_blocked_by') and args.remove_blocked_by:
        blocker_ids = [bid.strip() for bid in args.remove_blocked_by.split(',')]

        for blocker_id_prefix in blocker_ids:
            blocker_task = next((t for t in tasks if t['id'].startswith(blocker_id_prefix)), None)
            if blocker_task:
                # Remove from current task's blocked_by list
                if 'blocked_by' in task and blocker_task['id'] in task['blocked_by']:
                    task['blocked_by'].remove(blocker_task['id'])
                    # If this was the only blocker, unblock the task
                    if not task['blocked_by'] and task['status'] == 'blocked':
                        task['status'] = 'open'
                        print(f"Task {get_short_id(task['id'])} is now unblocked.")

                # Remove from blocker task's blocks list
                if 'blocks' in blocker_task and task['id'] in blocker_task['blocks']:
                    blocker_task['blocks'].remove(task['id'])
                    blocker_task['updated_at'] = now

                updated = True
                print(f"Removed blocker: {get_short_id(blocker_task['id'])} no longer blocks {get_short_id(task['id'])}")
            else:
                print(f"Warning: Blocker task '{blocker_id_prefix}' not found. Ignoring.", file=sys.stderr)

    if hasattr(args, 'status') and args.status:
        if args.status not in ['open', 'in_progress', 'done', 'blocked']:
            print(f"Error: Invalid status '{args.status}'.", file=sys.stderr)
            return
        task['status'] = args.status
        updated = True
        print(f"Updated status to '{task['status']}'")

        # --- Automatic Dependency Graph Update ---
        # If this task is marked 'done', we need to check if it unblocks other tasks.
        if task['status'] == 'done' and task.get('blocks'):
            all_task_ids = {t['id']: t for t in tasks}
            for blocked_task_id in task['blocks']:
                blocked_task = all_task_ids.get(blocked_task_id)
                if not blocked_task:
                    continue

                # Remove this task from the blocked_by list
                if task['id'] in blocked_task.get('blocked_by', []):
                    blocked_task['blocked_by'].remove(task['id'])
                    blocked_task['updated_at'] = now

                    # If it has no more blockers, set to 'open'
                    if not blocked_task['blocked_by'] and blocked_task['status'] == 'blocked':
                        blocked_task['status'] = 'open'
                        print(f"Task {get_short_id(blocked_task['id'])} is now unblocked.")

    if updated:
        db_save_tasks(tasks)
    else:
        print("No changes specified.")

def cmd_show(args):
    """'show' command: Display detailed information about a task."""
    task, _ = find_task(args.id)
    if not task:
        return

    print(f"\n{'='*70}")
    print(f"Task ID: {task['id']}")
    print(f"{'='*70}")
    print(f"Title: {task['title']}")
    print(f"Status: {task['status']}")
    if task.get('description'):
        print(f"\nDescription:\n{task['description']}")
    print(f"\nCreated: {task['created_at']}")
    print(f"Updated: {task['updated_at']}")

    # Show dependencies
    if task.get('blocks'):
        print(f"\nBlocks: {', '.join([get_short_id(tid) for tid in task['blocks']])}")
    if task.get('blocked_by'):
        print(f"Blocked by: {', '.join([get_short_id(tid) for tid in task['blocked_by']])}")

    # Show session logs
    sessions = task.get('sessions', [])
    if sessions:
        print(f"\n{'─'*70}")
        print(f"Session Logs ({len(sessions)} entries):")
        print(f"{'─'*70}")
        for i, session in enumerate(sessions, 1):
            timestamp = session['timestamp']
            log = session['log']
            print(f"\n[{i}] {timestamp}")
            print(f"{log}")
    else:
        print(f"\nNo session logs yet.")

    print(f"\n{'='*70}\n")

def cmd_delete(args):
    """'delete' command: Removes a task from the database."""
    task, tasks = find_task(args.id)
    if not task:
        return

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    task_id = task['id']
    task_title = task['title']

    # Remove this task from all tasks' dependency lists
    for other_task in tasks:
        if other_task['id'] == task_id:
            continue

        # Remove from blocks lists
        if 'blocks' in other_task and task_id in other_task['blocks']:
            other_task['blocks'].remove(task_id)
            other_task['updated_at'] = now

        # Remove from blocked_by lists
        if 'blocked_by' in other_task and task_id in other_task['blocked_by']:
            other_task['blocked_by'].remove(task_id)
            other_task['updated_at'] = now
            # If this was the only blocker, unblock the task
            if not other_task['blocked_by'] and other_task['status'] == 'blocked':
                other_task['status'] = 'open'
                print(f"Task {get_short_id(other_task['id'])} is now unblocked.")

    # Remove the task itself from the list
    tasks = [t for t in tasks if t['id'] != task_id]

    # Save the updated task list
    db_save_tasks(tasks)
    print(f"Deleted task {get_short_id(task_id)}: {task_title}")

# --- Web UI Handler ---

class WebUIHandler(http.server.SimpleHTTPRequestHandler):
    """
    Custom HTTP handler to serve the web UI.
    - GET /: Serves the main HTML page.
    - GET /api/tasks: Returns all tasks as JSON.
    - GET /api/update?id=...&status=...: Updates a task and redirects to /.
    """

    def _send_response(self, content, content_type="text/html", status=200):
        self.send_response(status)
        self.send_header("Content-type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def _get_web_html(self):
        """Returns the single-page application HTML as a string."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>readyq UI</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; color: #333; margin: 0; }
                header { background: #fff; border-bottom: 1px solid #ddd; padding: 1rem 2rem; font-size: 1.5rem; font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
                main { max-width: 900px; margin: 2rem auto; padding: 1rem; }
                .task-list { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
                .task { display: flex; align-items: center; padding: 1rem; border-bottom: 1px solid #eee; }
                .task:last-child { border-bottom: none; }
                .task-id { font-family: monospace; font-size: 0.9em; color: #888; width: 80px; }
                .task-title { flex-grow: 1; font-weight: 500; }
                .task-status { font-family: monospace; font-size: 0.9em; padding: 0.25rem 0.5rem; border-radius: 4px; text-transform: capitalize; width: 100px; text-align: center;}
                .status-open { background: #e6f7ff; border: 1px solid #91d5ff; color: #096dd9; }
                .status-in_progress { background: #fffbe6; border: 1px solid #ffe58f; color: #d48806; }
                .status-blocked { background: #fff1f0; border: 1px solid #ffa39e; color: #cf1322; }
                .status-done { background: #f6ffed; border: 1px solid #b7eb8f; color: #389e0d; text-decoration: line-through; }
                .task-actions a { text-decoration: none; color: #1890ff; margin-left: 1rem; font-size: 0.9em; cursor: pointer; }

                /* Modal styles */
                .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); overflow-y: auto; }
                .modal-content { background: #fff; margin: 2rem auto; padding: 2rem; width: 80%; max-width: 600px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-height: calc(100vh - 4rem); overflow-y: auto; }
                .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; position: sticky; top: 0; background: #fff; z-index: 10; padding-bottom: 0.5rem; border-bottom: 1px solid #eee; }
                .modal-header h2 { margin: 0; }
                .modal-close { cursor: pointer; font-size: 1.5rem; color: #888; border: none; background: none; }
                .modal-close:hover { color: #333; }

                /* Form styles */
                .form-group { margin-bottom: 1rem; }
                .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
                .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; font-family: inherit; box-sizing: border-box; }
                .form-group textarea { min-height: 100px; resize: vertical; }
                .form-group small { display: block; margin-top: 0.25rem; color: #888; font-size: 0.85em; }
                .form-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1.5rem; }
                .btn { padding: 0.5rem 1rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em; font-weight: 500; }
                .btn-primary { background: #1890ff; color: #fff; }
                .btn-primary:hover { background: #096dd9; }
                .btn-secondary { background: #f0f0f0; color: #333; }
                .btn-secondary:hover { background: #d9d9d9; }

                .new-task-btn { background: #52c41a; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; font-weight: 500; }
                .new-task-btn:hover { background: #389e0d; }

                .session-logs { margin-top: 1rem; padding: 1rem; background: #f9f9f9; border-radius: 4px; max-height: 200px; overflow-y: auto; }
                .session-log { margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #eee; display: flex; flex-direction: column; }
                .session-log:last-child { border-bottom: none; }
                .session-log-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; }
                .session-log-timestamp { font-weight: 500; font-size: 0.85em; color: #888; }
                .session-log-delete { cursor: pointer; color: #ff4d4f; font-size: 0.85em; text-decoration: none; padding: 0.25rem 0.5rem; border-radius: 3px; }
                .session-log-delete:hover { background: #fff1f0; }
                .session-log-content { font-size: 0.9em; white-space: pre-wrap; }
            </style>
        </head>
        <body>
            <header>
                <span>readyq Tasks</span>
                <button class="new-task-btn" onclick="openCreateModal()">+ New Task</button>
            </header>
            <main>
                <h2>Ready Tasks</h2>
                <div id="ready-tasks" class="task-list"></div>

                <h2>All Other Tasks</h2>
                <div id="other-tasks" class="task-list"></div>
            </main>

            <!-- Create Task Modal -->
            <div id="create-modal" class="modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Create New Task</h2>
                        <button class="modal-close" onclick="closeCreateModal()">&times;</button>
                    </div>
                    <form id="create-form" action="/api/create" method="POST">
                        <div class="form-group">
                            <label for="create-title">Title *</label>
                            <input type="text" id="create-title" name="title" required>
                        </div>
                        <div class="form-group">
                            <label for="create-description">Description</label>
                            <textarea id="create-description" name="description"></textarea>
                        </div>
                        <div class="form-group">
                            <label for="create-blocked-by">Blocked By</label>
                            <input type="text" id="create-blocked-by" name="blocked_by" placeholder="Comma-separated task IDs or prefixes">
                            <small>Enter task IDs (or prefixes) that must be completed before this task</small>
                        </div>
                        <div class="form-actions">
                            <button type="button" class="btn btn-secondary" onclick="closeCreateModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Create Task</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Edit Task Modal -->
            <div id="edit-modal" class="modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Edit Task</h2>
                        <button class="modal-close" onclick="closeEditModal()">&times;</button>
                    </div>
                    <form id="edit-form" action="/api/edit" method="POST">
                        <input type="hidden" id="edit-id" name="id">
                        <div class="form-group">
                            <label for="edit-title">Title</label>
                            <input type="text" id="edit-title" name="title">
                        </div>
                        <div class="form-group">
                            <label for="edit-description">Description</label>
                            <textarea id="edit-description" name="description"></textarea>
                        </div>
                        <div class="form-group">
                            <label for="edit-status">Status</label>
                            <select id="edit-status" name="status">
                                <option value="">-- No change --</option>
                                <option value="open">Open</option>
                                <option value="in_progress">In Progress</option>
                                <option value="blocked">Blocked</option>
                                <option value="done">Done</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="edit-add-blocks">Add Blocks</label>
                            <input type="text" id="edit-add-blocks" name="add_blocks" placeholder="Comma-separated task IDs">
                            <small>Tasks that this task will block</small>
                        </div>
                        <div class="form-group">
                            <label for="edit-add-blocked-by">Add Blocked By</label>
                            <input type="text" id="edit-add-blocked-by" name="add_blocked_by" placeholder="Comma-separated task IDs">
                            <small>Tasks that will block this task</small>
                        </div>
                        <div class="form-group">
                            <label for="edit-log">Add Session Log</label>
                            <textarea id="edit-log" name="log" placeholder="What did you learn or accomplish?"></textarea>
                        </div>
                        <div id="edit-session-logs"></div>
                        <div class="form-actions">
                            <button type="button" class="btn btn-secondary" onclick="closeEditModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Save Changes</button>
                        </div>
                    </form>
                </div>
            </div>

            <script>
                let allTasks = [];

                async function loadTasks() {
                    const response = await fetch('/api/tasks');
                    allTasks = await response.json();

                    const readyList = document.getElementById('ready-tasks');
                    const otherList = document.getElementById('other-tasks');
                    readyList.innerHTML = '';
                    otherList.innerHTML = '';

                    // Determine "ready" state client-side
                    const taskMap = new Map(allTasks.map(t => [t.id, t]));

                    const getIsReady = (task) => {
                        if (task.status === 'done') return false;
                        if (!task.blocked_by || task.blocked_by.length === 0) return true;
                        return task.blocked_by.every(id => taskMap.get(id)?.status === 'done');
                    };

                    allTasks.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

                    allTasks.forEach(task => {
                        const isReady = getIsReady(task);
                        const list = isReady ? readyList : otherList;

                        const actions = [
                            `<a onclick="openEditModal('${task.id}')">Edit</a>`,
                            task.status !== 'in_progress' ? `<a href="/api/update?id=${task.id}&status=in_progress">Start</a>` : '',
                            task.status !== 'done' ? `<a href="/api/update?id=${task.id}&status=done">Done</a>` : '',
                            task.status === 'done' ? `<a href="/api/update?id=${task.id}&status=open">Re-open</a>` : '',
                            `<a onclick="deleteTask('${task.id}', '${escapeHtml(task.title).replace(/'/g, '\\\'')}')" style="color: #ff4d4f;">Delete</a>`
                        ].filter(a => a).join(' ');

                        list.innerHTML += `
                            <div class="task">
                                <div class="task-id">${task.id.substring(0, 8)}</div>
                                <div class="task-title">${escapeHtml(task.title)}</div>
                                <div class="task-status status-${task.status.replace('_', '-')}">${task.status}</div>
                                <div class="task-actions">${actions}</div>
                            </div>
                        `;
                    });
                }

                function escapeHtml(text) {
                    const div = document.createElement('div');
                    div.textContent = text;
                    return div.innerHTML;
                }

                function openCreateModal() {
                    document.getElementById('create-modal').style.display = 'block';
                    document.getElementById('create-form').reset();
                }

                function closeCreateModal() {
                    document.getElementById('create-modal').style.display = 'none';
                }

                function openEditModal(taskId) {
                    const task = allTasks.find(t => t.id === taskId);
                    if (!task) return;

                    document.getElementById('edit-id').value = task.id;
                    document.getElementById('edit-title').value = task.title;
                    document.getElementById('edit-description').value = task.description || '';
                    document.getElementById('edit-status').value = '';
                    document.getElementById('edit-add-blocks').value = '';
                    document.getElementById('edit-add-blocked-by').value = '';
                    document.getElementById('edit-log').value = '';

                    // Display existing session logs
                    const logsContainer = document.getElementById('edit-session-logs');
                    if (task.sessions && task.sessions.length > 0) {
                        const logsHtml = task.sessions.map((s, i) => `
                            <div class="session-log" data-log-index="${i}">
                                <div class="session-log-header">
                                    <div class="session-log-timestamp">[${i+1}] ${new Date(s.timestamp).toLocaleString()}</div>
                                    <a class="session-log-delete" onclick="deleteSessionLog('${task.id}', ${i})">Delete</a>
                                </div>
                                <div class="session-log-content">${escapeHtml(s.log)}</div>
                            </div>
                        `).join('');
                        logsContainer.innerHTML = '<div class="form-group"><label>Existing Session Logs</label><div class="session-logs">' + logsHtml + '</div></div>';
                    } else {
                        logsContainer.innerHTML = '';
                    }

                    document.getElementById('edit-modal').style.display = 'block';
                }

                function closeEditModal() {
                    document.getElementById('edit-modal').style.display = 'none';
                }

                async function deleteSessionLog(taskId, logIndex) {
                    if (!confirm('Are you sure you want to delete this session log?')) {
                        return;
                    }

                    try {
                        const response = await fetch('/api/delete-log', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded',
                            },
                            body: `id=${encodeURIComponent(taskId)}&log_index=${logIndex}`
                        });

                        if (response.ok) {
                            // Reload tasks and reopen the edit modal
                            await loadTasks();
                            openEditModal(taskId);
                        } else {
                            alert('Failed to delete session log');
                        }
                    } catch (error) {
                        alert('Error deleting session log: ' + error.message);
                    }
                }

                async function deleteTask(taskId, taskTitle) {
                    if (!confirm(`Are you sure you want to delete task "${taskTitle}"?\n\nThis will also remove all dependency relationships with other tasks.`)) {
                        return;
                    }

                    try {
                        const response = await fetch('/api/delete', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded',
                            },
                            body: `id=${encodeURIComponent(taskId)}`
                        });

                        if (response.ok || response.redirected) {
                            // Redirect to home or reload tasks
                            window.location.href = '/';
                        } else {
                            alert('Failed to delete task');
                        }
                    } catch (error) {
                        alert('Error deleting task: ' + error.message);
                    }
                }

                // Close modals when clicking outside
                window.onclick = function(event) {
                    const createModal = document.getElementById('create-modal');
                    const editModal = document.getElementById('edit-modal');
                    if (event.target === createModal) {
                        closeCreateModal();
                    }
                    if (event.target === editModal) {
                        closeEditModal();
                    }
                }

                document.addEventListener('DOMContentLoaded', loadTasks);
            </script>
        </body>
        </html>
        """

    def do_GET(self):
        """Handle GET requests."""
        url = urlparse(self.path)

        if url.path == '/':
            self._send_response(self._get_web_html())

        elif url.path == '/api/tasks':
            try:
                tasks = db_load_tasks()
                self._send_response(json.dumps(tasks), content_type="application/json")
            except Exception as e:
                self._send_response(json.dumps({"error": str(e)}), content_type="application/json", status=500)

        elif url.path == '/api/update':
            params = parse_qs(url.query)
            task_id = params.get('id', [None])[0]
            status = params.get('status', [None])[0]

            if not task_id or not status:
                self._send_response(json.dumps({"error": "Missing 'id' or 'status'"}), content_type="application/json", status=400)
                return

            # --- This is a bit of a hack ---
            # We are re-using the CLI update logic inside the web server.
            # This is not ideal (e.g., stdout/stderr), but works for "no-dependencies".
            class FakeArgs:
                def __init__(self, id, status, log=None):
                    self.id = id
                    self.status = status
                    self.log = log

            try:
                cmd_update(FakeArgs(id=task_id, status=status, log=None))
                # Redirect back to the main page
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            except Exception as e:
                self._send_response(json.dumps({"error": str(e)}), content_type="application/json", status=500)

        else:
            # Fallback for other files (e.g., /favicon.ico)
            self._send_response("Not Found", status=404)

    def do_POST(self):
        """Handle POST requests for create and edit operations."""
        from urllib.parse import parse_qs

        url = urlparse(self.path)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = parse_qs(post_data.decode('utf-8'))

        # Helper to get first value from params
        def get_param(name, default=None):
            values = params.get(name, [default])
            return values[0] if values and values[0] else default

        if url.path == '/api/create':
            # Create new task
            title = get_param('title')
            description = get_param('description', '')
            blocked_by = get_param('blocked_by', '')

            if not title:
                self._send_response(json.dumps({"error": "Missing 'title'"}), content_type="application/json", status=400)
                return

            # Create FakeArgs for cmd_new
            class CreateArgs:
                def __init__(self):
                    self.title = title
                    self.description = description
                    self.blocked_by = blocked_by if blocked_by else None

            try:
                cmd_new(CreateArgs())
                # Redirect back to the main page
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            except Exception as e:
                self._send_response(json.dumps({"error": str(e)}), content_type="application/json", status=500)

        elif url.path == '/api/edit':
            # Edit existing task
            task_id = get_param('id')
            title = get_param('title')
            description = get_param('description')
            status = get_param('status')
            add_blocks = get_param('add_blocks')
            add_blocked_by = get_param('add_blocked_by')
            log = get_param('log')

            if not task_id:
                self._send_response(json.dumps({"error": "Missing 'id'"}), content_type="application/json", status=400)
                return

            # Create FakeArgs for cmd_update
            class EditArgs:
                def __init__(self):
                    self.id = task_id
                    self.title = title if title else None
                    self.description = description if description is not None else None
                    self.status = status if status else None
                    self.add_blocks = add_blocks if add_blocks else None
                    self.add_blocked_by = add_blocked_by if add_blocked_by else None
                    self.log = log if log else None

            try:
                cmd_update(EditArgs())
                # Redirect back to the main page
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            except Exception as e:
                self._send_response(json.dumps({"error": str(e)}), content_type="application/json", status=500)

        elif url.path == '/api/delete-log':
            # Delete a session log by index
            task_id = get_param('id')
            log_index = get_param('log_index')

            if not task_id or log_index is None:
                self._send_response(json.dumps({"error": "Missing 'id' or 'log_index'"}), content_type="application/json", status=400)
                return

            try:
                log_index = int(log_index)

                # Find the task
                task, tasks = find_task(task_id)
                if not task:
                    self._send_response(json.dumps({"error": "Task not found"}), content_type="application/json", status=404)
                    return

                # Check if log index is valid
                if 'sessions' not in task or log_index < 0 or log_index >= len(task['sessions']):
                    self._send_response(json.dumps({"error": "Invalid log index"}), content_type="application/json", status=400)
                    return

                # Delete the log entry
                task['sessions'].pop(log_index)
                task['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

                # Save the updated tasks
                db_save_tasks(tasks)

                # Return success
                self._send_response(json.dumps({"success": True}), content_type="application/json")
            except ValueError:
                self._send_response(json.dumps({"error": "Invalid log_index format"}), content_type="application/json", status=400)
            except Exception as e:
                self._send_response(json.dumps({"error": str(e)}), content_type="application/json", status=500)

        elif url.path == '/api/delete':
            # Delete a task
            task_id = get_param('id')

            if not task_id:
                self._send_response(json.dumps({"error": "Missing 'id'"}), content_type="application/json", status=400)
                return

            # Create FakeArgs for cmd_delete
            class DeleteArgs:
                def __init__(self):
                    self.id = task_id

            try:
                cmd_delete(DeleteArgs())
                # Redirect back to the main page
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            except Exception as e:
                self._send_response(json.dumps({"error": str(e)}), content_type="application/json", status=500)

        else:
            self._send_response("Not Found", status=404)

def cmd_web(args):
    """'web' command: Starts the web server."""

    Handler = WebUIHandler
    # Use ThreadingTCPServer to handle concurrent requests
    with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
        url = f"http://{HOST}:{PORT}"
        print(f"Serving web UI at {url}")
        print("Press Ctrl+C to stop.")

        # Open the web browser in a new thread
        threading.Timer(1, lambda: webbrowser.open_new_tab(url)).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            httpd.shutdown()
            sys.exit(0)

# --- Main CLI Parsing ---

def main():
    parser = argparse.ArgumentParser(
        description="readyq: A dependency-aware task tracker using a JSONL file."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-command to run")

    # 'quickstart' command
    subparsers.add_parser(
        "quickstart",
        help="Initialize the .readyq.jsonl file in the current directory."
    ).set_defaults(func=cmd_quickstart)

    # 'new' command
    parser_new = subparsers.add_parser("new", help="Create a new task.")
    parser_new.add_argument("title", type=str, help="The title of the task.")
    parser_new.add_argument("--description", type=str, help="Detailed description of the task.")
    parser_new.add_argument("--blocked-by", type=str, help="Comma-separated list of task IDs that block this one.")
    parser_new.set_defaults(func=cmd_new)

    # 'list' command
    parser_list = subparsers.add_parser("list", help="List all tasks.")
    parser_list.set_defaults(func=cmd_list)

    # 'ready' command
    parser_ready = subparsers.add_parser("ready", help="List all tasks that are 'open' and not blocked.")
    parser_ready.set_defaults(func=cmd_ready)

    # 'update' command
    parser_update = subparsers.add_parser("update", help="Update a task.")
    parser_update.add_argument("id", type=str, help="The ID (or prefix) of the task to update.")
    parser_update.add_argument("--title", type=str, help="Update the task title.")
    parser_update.add_argument("--description", type=str, help="Update the task description.")
    parser_update.add_argument("--status", type=str, choices=['open', 'in_progress', 'done', 'blocked'], help="Set a new status.")
    parser_update.add_argument("--log", type=str, help="Add a session log entry to the task.")
    parser_update.add_argument("--delete-log", type=int, metavar="INDEX", help="Delete a session log by index (0-based).")
    parser_update.add_argument("--add-blocks", type=str, help="Add task IDs that this task blocks (comma-separated).")
    parser_update.add_argument("--add-blocked-by", type=str, help="Add task IDs that block this task (comma-separated).")
    parser_update.add_argument("--remove-blocks", type=str, help="Remove task IDs that this task blocks (comma-separated).")
    parser_update.add_argument("--remove-blocked-by", type=str, help="Remove task IDs that block this task (comma-separated).")
    parser_update.set_defaults(func=cmd_update)

    # 'show' command
    parser_show = subparsers.add_parser("show", help="Show detailed information about a task.")
    parser_show.add_argument("id", type=str, help="The ID (or prefix) of the task to show.")
    parser_show.set_defaults(func=cmd_show)

    # 'delete' command
    parser_delete = subparsers.add_parser("delete", help="Delete a task.")
    parser_delete.add_argument("id", type=str, help="The ID (or prefix) of the task to delete.")
    parser_delete.set_defaults(func=cmd_delete)

    # 'web' command
    parser_web = subparsers.add_parser("web", help="Start the web UI server.")
    parser_web.set_defaults(func=cmd_web)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

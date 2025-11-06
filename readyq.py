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
    """'quickstart' command: Initializes the DB and displays tutorial for AI agents."""
    # Initialize database if it doesn't exist
    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'w').close()
        print(f"Initialized empty readyq file at '{DB_FILE}'.\n")

    # Display comprehensive tutorial for AI agents
    tutorial = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     READYQ TASK TRACKING SYSTEM                              ║
║                      Quickstart Guide for AI Agents                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

OVERVIEW
────────
readyq is a CLI-based task management tool for tracking work items and
dependencies. It helps you organize tasks, manage blockers, and maintain
persistent context across work sessions.

CORE WORKFLOW
─────────────

1. CREATING TASKS
   Add new work items with titles and optional descriptions:

   ./readyq.py new "Set up database schema"
   ./readyq.py new "Build API endpoints" --description "REST API for user management"

2. MANAGING DEPENDENCIES
   Link tasks to show blocking relationships (task A must complete before B):

   ./readyq.py new "Write tests" --blocked-by <task-id>
   ./readyq.py update <task-id> --add-blocked-by <blocker-id>
   ./readyq.py update <task-id> --add-blocks <dependent-id>

3. FINDING ACTIONABLE WORK
   See unblocked tasks ready for immediate action:

   ./readyq.py ready

   This shows only tasks with status != 'done' and no active blockers.

4. TRACKING PROGRESS
   Update status as you work:

   ./readyq.py update <task-id> --status in_progress
   ./readyq.py update <task-id> --status done

   When a task is marked 'done', all tasks it blocks are automatically unblocked.

5. PERSISTENT MEMORY (AI Agent Feature)
   Track what you learned or accomplished in each session:

   ./readyq.py update <task-id> --log "Discovered the auth module uses JWT tokens"
   ./readyq.py show <task-id>  # View full task details with all session logs

COMMON COMMANDS
───────────────

List all tasks:          ./readyq.py list
View ready tasks:        ./readyq.py ready
Show task details:       ./readyq.py show <task-id>
Update task status:      ./readyq.py update <task-id> --status [open|in_progress|done|blocked]
Update title/desc:       ./readyq.py update <task-id> --title "New title" --description "New desc"
Add session log:         ./readyq.py update <task-id> --log "What you learned"
Delete log entry:        ./readyq.py update <task-id> --delete-log <index>
Delete task:             ./readyq.py delete <task-id>
Web interface:           ./readyq.py web

TASK STATUSES
─────────────

• open          - Ready to start (no active blockers)
• in_progress   - Currently being worked on
• blocked       - Waiting on dependencies
• done          - Completed

PRACTICAL EXAMPLE
─────────────────

# Start a new project
./readyq.py quickstart

# Create foundation task
./readyq.py new "Research codebase architecture"
TASK1_ID=$(./readyq.py list | tail -1 | awk '{print $1}')

# Create dependent tasks
./readyq.py new "Design database schema" --blocked-by $TASK1_ID
TASK2_ID=$(./readyq.py list | tail -1 | awk '{print $1}')
./readyq.py new "Implement API" --blocked-by $TASK2_ID

# Check what's ready
./readyq.py ready  # Shows only "Research codebase architecture"

# Work on first task
./readyq.py update $TASK1_ID --status in_progress
./readyq.py update $TASK1_ID --log "Found main entry point in server.py"
./readyq.py update $TASK1_ID --log "Auth system uses custom JWT implementation"

# Complete task (automatically unblocks next task)
./readyq.py update $TASK1_ID --status done

# Check what's ready now
./readyq.py ready  # Now shows "Design database schema"

TIPS FOR AI AGENTS
──────────────────

1. Use --log frequently to maintain context between sessions
2. Always check './readyq.py ready' before starting new work
3. Partial task IDs work (e.g., 'c4a0' instead of full UUID)
4. Mark tasks 'done' when complete to unblock dependent tasks
5. Use descriptions for detailed task context
6. View full history with './readyq.py show <task-id>'
7. The web UI ('./readyq.py web') provides visual task management

DATABASE LOCATION
─────────────────

Default: ./.readyq.jsonl (in current directory)
Format:  JSONL (one JSON task per line, git-friendly)

NEXT STEPS
──────────

1. Run './readyq.py list' to see all tasks
2. Run './readyq.py ready' to find actionable work
3. Run './readyq.py web' to explore the visual interface

For detailed help: ./readyq.py --help
For command help:  ./readyq.py <command> --help

╔══════════════════════════════════════════════════════════════════════════════╗
║  TIP: This quickstart guide is always available via './readyq.py quickstart'║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(tutorial)

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
        return r"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>readyq UI</title>
            <style>
                /* Design System - Color Palette */
                :root {
                    --color-bg-primary: #fafbfc;
                    --color-bg-secondary: #ffffff;
                    --color-bg-tertiary: #f6f8fa;

                    --color-text-primary: #1f2937;
                    --color-text-secondary: #6b7280;
                    --color-text-tertiary: #9ca3af;

                    --color-border: #e5e7eb;
                    --color-border-hover: #d1d5db;

                    --color-brand: #6366f1;
                    --color-brand-hover: #4f46e5;
                    --color-brand-light: #eef2ff;

                    --color-success: #10b981;
                    --color-success-bg: #ecfdf5;
                    --color-success-border: #a7f3d0;

                    --color-warning: #f59e0b;
                    --color-warning-bg: #fffbeb;
                    --color-warning-border: #fde68a;

                    --color-danger: #ef4444;
                    --color-danger-bg: #fef2f2;
                    --color-danger-border: #fecaca;

                    --color-info: #3b82f6;
                    --color-info-bg: #eff6ff;
                    --color-info-border: #bfdbfe;

                    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
                    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);

                    --radius-sm: 6px;
                    --radius-md: 8px;
                    --radius-lg: 12px;

                    --transition: all 0.15s ease;
                }

                /* Base Styles */
                * {
                    box-sizing: border-box;
                }

                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", "SF Pro Display", Helvetica, Arial, sans-serif;
                    background: var(--color-bg-primary);
                    color: var(--color-text-primary);
                    margin: 0;
                    line-height: 1.6;
                    -webkit-font-smoothing: antialiased;
                    -moz-osx-font-smoothing: grayscale;
                }

                /* Header */
                header {
                    background: var(--color-bg-secondary);
                    border-bottom: 1px solid var(--color-border);
                    padding: 1.25rem 2rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    box-shadow: var(--shadow-sm);
                    position: sticky;
                    top: 0;
                    z-index: 100;
                }

                header span {
                    font-size: 1.5rem;
                    font-weight: 700;
                    letter-spacing: -0.02em;
                    color: var(--color-text-primary);
                }

                /* Main Layout */
                main {
                    max-width: 960px;
                    margin: 2.5rem auto;
                    padding: 0 1.5rem;
                }

                main h2 {
                    font-size: 1.125rem;
                    font-weight: 600;
                    color: var(--color-text-primary);
                    margin: 2rem 0 1rem 0;
                    letter-spacing: -0.01em;
                }

                main h2:first-child {
                    margin-top: 0;
                }

                /* Task List */
                .task-list {
                    background: var(--color-bg-secondary);
                    border-radius: var(--radius-lg);
                    border: 1px solid var(--color-border);
                    overflow: hidden;
                }

                .task {
                    display: flex;
                    align-items: center;
                    padding: 1rem 1.25rem;
                    gap: 1rem;
                    border-bottom: 1px solid var(--color-border);
                    transition: var(--transition);
                }

                .task:last-child {
                    border-bottom: none;
                }

                .task:hover {
                    background: var(--color-bg-tertiary);
                }

                .task-id {
                    font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", "Courier New", monospace;
                    font-size: 0.8125rem;
                    color: var(--color-text-tertiary);
                    width: 72px;
                    flex-shrink: 0;
                    font-weight: 500;
                }

                .task-title {
                    flex-grow: 1;
                    font-weight: 500;
                    color: var(--color-text-primary);
                    min-width: 0;
                    font-size: 0.9375rem;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }

                /* Status Badges */
                .task-status {
                    font-family: inherit;
                    font-size: 0.8125rem;
                    font-weight: 600;
                    padding: 0.375rem 0.875rem;
                    border-radius: 9999px;
                    width: 110px;
                    text-align: center;
                    flex-shrink: 0;
                    white-space: nowrap;
                    letter-spacing: 0.01em;
                    transition: var(--transition);
                }

                .status-open {
                    background: var(--color-info-bg);
                    color: var(--color-info);
                    border: 1px solid var(--color-info-border);
                }

                .status-in-progress {
                    background: var(--color-warning-bg);
                    color: var(--color-warning);
                    border: 1px solid var(--color-warning-border);
                }

                .status-blocked {
                    background: var(--color-danger-bg);
                    color: var(--color-danger);
                    border: 1px solid var(--color-danger-border);
                }

                .status-done {
                    background: var(--color-success-bg);
                    color: var(--color-success);
                    border: 1px solid var(--color-success-border);
                }

                /* Task Actions */
                .task-actions {
                    flex-shrink: 0;
                    white-space: nowrap;
                    display: flex;
                    gap: 0.75rem;
                    width: 280px;
                    justify-content: flex-end;
                }

                .task-actions a {
                    text-decoration: none;
                    color: var(--color-brand);
                    font-size: 0.875rem;
                    cursor: pointer;
                    font-weight: 500;
                    transition: var(--transition);
                    padding: 0.25rem 0.5rem;
                    border-radius: var(--radius-sm);
                }

                .task-actions a:hover {
                    background: var(--color-brand-light);
                    color: var(--color-brand-hover);
                }

                .task-actions a[style*="color: #ff4d4f"] {
                    color: var(--color-danger) !important;
                }

                .task-actions a[style*="color: #ff4d4f"]:hover {
                    background: var(--color-danger-bg);
                }

                /* Buttons */
                .new-task-btn {
                    background: var(--color-brand);
                    color: white;
                    border: none;
                    padding: 0.625rem 1.25rem;
                    border-radius: var(--radius-md);
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 0.9375rem;
                    transition: var(--transition);
                    box-shadow: var(--shadow-sm);
                }

                .new-task-btn:hover {
                    background: var(--color-brand-hover);
                    box-shadow: var(--shadow-md);
                    transform: translateY(-1px);
                }

                .new-task-btn:active {
                    transform: translateY(0);
                }

                /* Modal Styles */
                .modal {
                    display: none;
                    position: fixed;
                    z-index: 1000;
                    left: 0;
                    top: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(17, 24, 39, 0.75);
                    backdrop-filter: blur(4px);
                    animation: fadeIn 0.2s ease;
                }

                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }

                .modal-content {
                    background: var(--color-bg-secondary);
                    width: 100%;
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    animation: slideIn 0.3s ease;
                }

                @keyframes slideIn {
                    from {
                        opacity: 0;
                        transform: scale(0.95);
                    }
                    to {
                        opacity: 1;
                        transform: scale(1);
                    }
                }

                .modal-header {
                    display: flex;
                    justify-content: flex-end;
                    align-items: center;
                    padding: 1.5rem 2rem;
                    background: var(--color-bg-secondary);
                    border-bottom: 1px solid var(--color-border);
                    flex-shrink: 0;
                }

                .modal-body {
                    display: grid;
                    grid-template-columns: 300px 1fr 400px;
                    gap: 2rem;
                    padding: 2rem;
                    overflow-y: auto;
                    flex: 1;
                }

                .modal-column {
                    display: flex;
                    flex-direction: column;
                    gap: 1.5rem;
                }

                .modal-column-title {
                    font-size: 1rem;
                    font-weight: 700;
                    color: var(--color-text-primary);
                    margin-bottom: 0.5rem;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    font-size: 0.875rem;
                }

                .modal-close {
                    cursor: pointer;
                    font-size: 2rem;
                    color: var(--color-text-tertiary);
                    border: none;
                    background: none;
                    padding: 0.5rem;
                    line-height: 1;
                    transition: var(--transition);
                    border-radius: var(--radius-sm);
                    width: 40px;
                    height: 40px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }

                .modal-close:hover {
                    color: var(--color-text-primary);
                    background: var(--color-bg-tertiary);
                }

                .modal-footer {
                    padding: 1.5rem 2rem;
                    background: var(--color-bg-secondary);
                    border-top: 1px solid var(--color-border);
                    display: flex;
                    justify-content: flex-end;
                    gap: 0.75rem;
                    flex-shrink: 0;
                    position: sticky;
                    bottom: 0;
                    z-index: 10;
                }

                .modal-content form {
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                }

                /* Form Styles */
                .form-group {
                    margin-bottom: 1.25rem;
                }

                .form-group label {
                    display: block;
                    margin-bottom: 0.5rem;
                    font-weight: 600;
                    font-size: 0.875rem;
                    color: var(--color-text-primary);
                    letter-spacing: 0.01em;
                }

                .form-group input:not(.autocomplete-input),
                .form-group textarea,
                .form-group select {
                    width: 100%;
                    padding: 0.625rem 0.875rem;
                    border: 1px solid var(--color-border);
                    border-radius: var(--radius-md);
                    font-family: inherit;
                    font-size: 0.9375rem;
                    transition: var(--transition);
                    background: var(--color-bg-secondary);
                    color: var(--color-text-primary);
                }

                .form-group input:not(.autocomplete-input):focus,
                .form-group textarea:focus,
                .form-group select:focus {
                    outline: none;
                    border-color: var(--color-brand);
                    box-shadow: 0 0 0 3px var(--color-brand-light);
                }

                .form-group textarea {
                    min-height: 120px;
                    resize: vertical;
                    line-height: 1.5;
                }

                .form-group textarea.full-height {
                    min-height: 400px;
                    height: 100%;
                }

                .form-group small {
                    display: block;
                    margin-top: 0.375rem;
                    color: var(--color-text-secondary);
                    font-size: 0.8125rem;
                    line-height: 1.4;
                }

                .form-actions {
                    display: flex;
                    gap: 0.75rem;
                    justify-content: flex-end;
                    margin-top: 2rem;
                    padding-top: 1.5rem;
                    border-top: 1px solid var(--color-border);
                }

                .btn {
                    padding: 0.625rem 1.25rem;
                    border: none;
                    border-radius: var(--radius-md);
                    cursor: pointer;
                    font-size: 0.9375rem;
                    font-weight: 600;
                    transition: var(--transition);
                    font-family: inherit;
                }

                .btn-primary {
                    background: var(--color-brand);
                    color: #fff;
                    box-shadow: var(--shadow-sm);
                }

                .btn-primary:hover {
                    background: var(--color-brand-hover);
                    box-shadow: var(--shadow-md);
                    transform: translateY(-1px);
                }

                .btn-primary:active {
                    transform: translateY(0);
                }

                .btn-secondary {
                    background: var(--color-bg-tertiary);
                    color: var(--color-text-primary);
                }

                .btn-secondary:hover {
                    background: var(--color-border);
                }

                /* Session Logs */
                .session-logs {
                    margin-top: 1rem;
                    padding: 1rem;
                    background: var(--color-bg-tertiary);
                    border-radius: var(--radius-md);
                    border: 1px solid var(--color-border);
                    max-height: 300px;
                    overflow-y: auto;
                }

                .session-log {
                    margin-bottom: 1rem;
                    padding-bottom: 1rem;
                    border-bottom: 1px solid var(--color-border);
                    display: flex;
                    flex-direction: column;
                }

                .session-log:last-child {
                    border-bottom: none;
                    margin-bottom: 0;
                    padding-bottom: 0;
                }

                .session-log-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 0.5rem;
                }

                .session-log-timestamp {
                    font-weight: 600;
                    font-size: 0.8125rem;
                    color: var(--color-text-secondary);
                }

                .session-log-delete {
                    cursor: pointer;
                    color: var(--color-danger);
                    font-size: 0.8125rem;
                    font-weight: 600;
                    text-decoration: none;
                    padding: 0.25rem 0.625rem;
                    border-radius: var(--radius-sm);
                    transition: var(--transition);
                }

                .session-log-delete:hover {
                    background: var(--color-danger-bg);
                }

                .session-log-content {
                    font-size: 0.875rem;
                    line-height: 1.6;
                    white-space: pre-wrap;
                    color: var(--color-text-primary);
                }

                /* Autocomplete Styles */
                .autocomplete-wrapper {
                    position: relative;
                    width: 100%;
                }

                .autocomplete-container {
                    min-height: 42px;
                    padding: 0.375rem 0.625rem;
                    border: 1px solid var(--color-border);
                    border-radius: var(--radius-md);
                    background: var(--color-bg-secondary);
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.375rem;
                    align-items: center;
                    cursor: text;
                    transition: var(--transition);
                }

                .autocomplete-container:focus-within {
                    border-color: var(--color-brand);
                    box-shadow: 0 0 0 3px var(--color-brand-light);
                }

                .autocomplete-tag {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.375rem;
                    padding: 0.25rem 0.625rem;
                    background: var(--color-brand-light);
                    color: var(--color-brand);
                    border-radius: 9999px;
                    font-size: 0.8125rem;
                    font-weight: 500;
                    font-family: inherit;
                    max-width: 250px;
                    white-space: nowrap;
                }

                .autocomplete-tag-id {
                    overflow: hidden;
                    text-overflow: ellipsis;
                }

                .autocomplete-tag-remove {
                    cursor: pointer;
                    font-size: 1rem;
                    line-height: 1;
                    padding: 0 0.125rem;
                    color: var(--color-brand);
                    transition: var(--transition);
                    font-weight: 700;
                }

                .autocomplete-tag-remove:hover {
                    color: var(--color-brand-hover);
                }

                .autocomplete-input {
                    flex: 1;
                    min-width: 150px;
                    border: none;
                    outline: none;
                    padding: 0.25rem;
                    font-family: inherit;
                    font-size: 0.9375rem;
                    background: transparent;
                    color: var(--color-text-primary);
                }

                .autocomplete-input:focus {
                    outline: none;
                    border: none;
                    box-shadow: none;
                }

                .autocomplete-input::placeholder {
                    color: var(--color-text-tertiary);
                }

                .autocomplete-dropdown {
                    position: absolute;
                    top: calc(100% + 4px);
                    left: 0;
                    right: 0;
                    background: var(--color-bg-secondary);
                    border: 1px solid var(--color-border);
                    border-radius: var(--radius-md);
                    box-shadow: var(--shadow-lg);
                    max-height: 240px;
                    overflow-y: auto;
                    z-index: 1100;
                    display: none;
                }

                .autocomplete-dropdown.show {
                    display: block;
                }

                .autocomplete-item {
                    padding: 0.625rem 0.875rem;
                    cursor: pointer;
                    transition: var(--transition);
                    border-bottom: 1px solid var(--color-border);
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }

                .autocomplete-item:last-child {
                    border-bottom: none;
                }

                .autocomplete-item:hover,
                .autocomplete-item.highlighted {
                    background: var(--color-bg-tertiary);
                }

                .autocomplete-item.selected {
                    background: var(--color-brand-light);
                }

                .autocomplete-item-id {
                    font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", monospace;
                    font-size: 0.8125rem;
                    color: var(--color-text-tertiary);
                    font-weight: 600;
                    min-width: 72px;
                }

                .autocomplete-item-title {
                    font-size: 0.875rem;
                    color: var(--color-text-primary);
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    flex: 1;
                }

                .autocomplete-empty {
                    padding: 1rem 0.875rem;
                    text-align: center;
                    color: var(--color-text-secondary);
                    font-size: 0.875rem;
                }

                .autocomplete-helper {
                    display: block;
                    margin-top: 0.375rem;
                    color: var(--color-text-secondary);
                    font-size: 0.8125rem;
                    line-height: 1.4;
                }
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
                        <button class="modal-close" onclick="closeCreateModal()">&times;</button>
                    </div>
                    <form id="create-form" action="/api/create" method="POST">
                        <div class="modal-body">
                            <div class="modal-column">
                                <div>
                                    <div class="modal-column-title">Title</div>
                                    <div class="form-group">
                                        <input type="text" id="create-title" name="title" required placeholder="Enter task title">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="create-blocked-by">Blocked By</label>
                                    <div id="create-blocked-by-autocomplete"></div>
                                    <input type="hidden" id="create-blocked-by" name="blocked_by">
                                </div>
                            </div>
                            <div class="modal-column">
                                <div class="modal-column-title">Description</div>
                                <div class="form-group" style="flex: 1; display: flex; flex-direction: column;">
                                    <textarea id="create-description" name="description" class="full-height" placeholder="Enter detailed task description..."></textarea>
                                </div>
                            </div>
                            <div class="modal-column">
                                <div class="modal-column-title">Session Logs</div>
                                <p style="color: var(--color-text-secondary); font-size: 0.875rem;">Session logs will be added after task creation.</p>
                            </div>
                        </div>
                        <div class="modal-footer">
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
                        <button class="modal-close" onclick="closeEditModal()">&times;</button>
                    </div>
                    <form id="edit-form" action="/api/edit" method="POST">
                        <input type="hidden" id="edit-id" name="id">
                        <div class="modal-body">
                            <div class="modal-column">
                                <div>
                                    <div class="modal-column-title">Title</div>
                                    <div class="form-group">
                                        <input type="text" id="edit-title" name="title" placeholder="Enter task title">
                                    </div>
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
                                    <label for="edit-add-blocks">Blocks</label>
                                    <div id="edit-add-blocks-autocomplete"></div>
                                    <input type="hidden" id="edit-add-blocks" name="add_blocks">
                                    <input type="hidden" id="edit-remove-blocks" name="remove_blocks">
                                </div>
                                <div class="form-group">
                                    <label for="edit-add-blocked-by">Blocked By</label>
                                    <div id="edit-add-blocked-by-autocomplete"></div>
                                    <input type="hidden" id="edit-add-blocked-by" name="add_blocked_by">
                                    <input type="hidden" id="edit-remove-blocked-by" name="remove_blocked_by">
                                </div>
                            </div>
                            <div class="modal-column">
                                <div class="modal-column-title">Description</div>
                                <div class="form-group" style="flex: 1; display: flex; flex-direction: column;">
                                    <textarea id="edit-description" name="description" class="full-height" placeholder="Enter detailed task description..."></textarea>
                                </div>
                            </div>
                            <div class="modal-column">
                                <div class="modal-column-title">Session Logs</div>
                                <div class="form-group">
                                    <label for="edit-log">Add New Log</label>
                                    <textarea id="edit-log" name="log" placeholder="What did you learn or accomplish?"></textarea>
                                </div>
                                <div id="edit-session-logs"></div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="closeEditModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Save Changes</button>
                        </div>
                    </form>
                </div>
            </div>

            <script>
                let allTasks = [];

                // Autocomplete Input Component
                class AutocompleteInput {
                    constructor(containerId, hiddenFieldId, removeFieldId = null, excludeTaskId = null) {
                        this.containerId = containerId;
                        this.hiddenFieldId = hiddenFieldId;
                        this.removeFieldId = removeFieldId;  // For tracking removals
                        this.excludeTaskId = excludeTaskId;
                        this.originalTags = [];  // Tags that existed when modal opened
                        this.selectedTags = [];  // Current tags
                        this.filteredTasks = [];
                        this.highlightedIndex = -1;
                        this.inputDebounceTimer = null;

                        this.render();
                        this.attachEventListeners();
                    }

                    render() {
                        const container = document.getElementById(this.containerId);
                        if (!container) return;

                        container.innerHTML = `
                            <div class="autocomplete-wrapper">
                                <div class="autocomplete-container" data-autocomplete-container>
                                    <input type="text"
                                           class="autocomplete-input"
                                           placeholder="Type to search tasks..."
                                           data-autocomplete-input
                                           autocomplete="off">
                                </div>
                                <div class="autocomplete-dropdown" data-autocomplete-dropdown></div>
                                <small class="autocomplete-helper">Search by task ID or title. Press Enter to select.</small>
                            </div>
                        `;

                        this.inputElement = container.querySelector('[data-autocomplete-input]');
                        this.containerElement = container.querySelector('[data-autocomplete-container]');
                        this.dropdownElement = container.querySelector('[data-autocomplete-dropdown]');
                    }

                    attachEventListeners() {
                        if (!this.inputElement || !this.containerElement || !this.dropdownElement) {
                            return;
                        }

                        // Input events
                        this.inputElement.addEventListener('input', (e) => this.handleInput(e));
                        this.inputElement.addEventListener('keydown', (e) => this.handleKeydown(e));
                        this.inputElement.addEventListener('focus', () => this.showDropdown());
                        this.inputElement.addEventListener('blur', (e) => {
                            // Delay to allow click events on dropdown items
                            setTimeout(() => this.hideDropdown(), 250);
                        });

                        // Container click to focus input
                        this.containerElement.addEventListener('click', (e) => {
                            // Don't focus if clicking on a tag remove button
                            if (!e.target.classList.contains('autocomplete-tag-remove')) {
                                this.inputElement.focus();
                            }
                        });

                        // Document click to close dropdown
                        document.addEventListener('click', (e) => {
                            if (!this.containerElement.contains(e.target) &&
                                !this.dropdownElement.contains(e.target)) {
                                this.hideDropdown();
                            }
                        });
                    }

                    handleInput(event) {
                        const query = event.target.value.trim();

                        // Debounce filtering
                        clearTimeout(this.inputDebounceTimer);
                        this.inputDebounceTimer = setTimeout(() => {
                            this.filterTasks(query);
                            this.renderDropdown();
                            this.showDropdown();
                        }, 150);
                    }

                    handleKeydown(event) {
                        const key = event.key;

                        if (key === 'ArrowDown') {
                            event.preventDefault();
                            this.highlightedIndex = Math.min(
                                this.highlightedIndex + 1,
                                this.filteredTasks.length - 1
                            );
                            this.renderDropdown();
                        } else if (key === 'ArrowUp') {
                            event.preventDefault();
                            this.highlightedIndex = Math.max(this.highlightedIndex - 1, -1);
                            this.renderDropdown();
                        } else if (key === 'Enter') {
                            event.preventDefault();
                            if (this.highlightedIndex >= 0 && this.highlightedIndex < this.filteredTasks.length) {
                                this.addTag(this.filteredTasks[this.highlightedIndex].id);
                            }
                        } else if (key === 'Escape') {
                            event.preventDefault();
                            this.hideDropdown();
                        } else if (key === 'Backspace' && this.inputElement.value === '') {
                            event.preventDefault();
                            this.removeLastTag();
                        }
                    }

                    filterTasks(query) {
                        const lowerQuery = query.toLowerCase();

                        // Get available tasks (exclude selected and current task)
                        const availableTasks = allTasks.filter(task => {
                            if (this.excludeTaskId && task.id === this.excludeTaskId) return false;
                            if (this.selectedTags.includes(task.id)) return false;
                            return true;
                        });

                        if (!query) {
                            this.filteredTasks = availableTasks;
                        } else {
                            this.filteredTasks = availableTasks.filter(task => {
                                return task.id.toLowerCase().includes(lowerQuery) ||
                                       (task.title && task.title.toLowerCase().includes(lowerQuery));
                            });
                        }

                        this.highlightedIndex = this.filteredTasks.length > 0 ? 0 : -1;
                    }

                    renderDropdown() {
                        if (!this.dropdownElement) return;

                        if (this.filteredTasks.length === 0) {
                            this.dropdownElement.innerHTML = `
                                <div class="autocomplete-empty">No matching tasks found</div>
                            `;
                        } else {
                            const itemsHtml = this.filteredTasks.map((task, index) => {
                                const highlightClass = index === this.highlightedIndex ? 'highlighted' : '';
                                const shortId = task.id.substring(0, 8);
                                const title = task.title.length > 50
                                    ? task.title.substring(0, 50) + '...'
                                    : task.title;

                                return `
                                    <div class="autocomplete-item ${highlightClass}"
                                         data-task-id="${task.id}"
                                         data-index="${index}">
                                        <span class="autocomplete-item-id">${shortId}</span>
                                        <span class="autocomplete-item-title">${escapeHtml(title)}</span>
                                    </div>
                                `;
                            }).join('');

                            this.dropdownElement.innerHTML = itemsHtml;

                            // Attach event handlers to each item
                            this.dropdownElement.querySelectorAll('.autocomplete-item').forEach(item => {
                                // Mouse enter for highlighting - just update class, don't re-render
                                item.addEventListener('mouseenter', () => {
                                    const index = parseInt(item.getAttribute('data-index'));
                                    this.highlightedIndex = index;
                                    // Update classes without re-rendering
                                    this.dropdownElement.querySelectorAll('.autocomplete-item').forEach((el, i) => {
                                        if (i === index) {
                                            el.classList.add('highlighted');
                                        } else {
                                            el.classList.remove('highlighted');
                                        }
                                    });
                                });

                                // Mousedown to prevent blur - MUST come before click
                                item.addEventListener('mousedown', (e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                });

                                // Click handler on item
                                item.addEventListener('click', (e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    const taskId = item.getAttribute('data-task-id');
                                    if (taskId) {
                                        this.addTag(taskId);
                                    }
                                });
                            });
                        }
                    }

                    showDropdown() {
                        if (!this.dropdownElement) return;

                        this.filterTasks(this.inputElement.value.trim());
                        this.renderDropdown();
                        this.dropdownElement.classList.add('show');
                    }

                    hideDropdown() {
                        if (!this.dropdownElement) return;
                        this.dropdownElement.classList.remove('show');
                    }

                    addTag(taskId) {
                        if (this.selectedTags.includes(taskId)) return;

                        this.selectedTags.push(taskId);
                        this.renderTags();
                        this.updateHiddenField();

                        // Clear input and refocus
                        this.inputElement.value = '';
                        this.inputElement.focus();
                        this.filterTasks('');
                        this.renderDropdown();
                    }

                    removeTag(taskId) {
                        this.selectedTags = this.selectedTags.filter(id => id !== taskId);
                        this.renderTags();
                        this.updateHiddenField();
                        this.inputElement.focus();
                    }

                    removeLastTag() {
                        if (this.selectedTags.length > 0) {
                            this.selectedTags.pop();
                            this.renderTags();
                            this.updateHiddenField();
                        }
                    }

                    renderTags() {
                        if (!this.containerElement || !this.inputElement) return;

                        // Remove existing tags
                        this.containerElement.querySelectorAll('.autocomplete-tag').forEach(tag => tag.remove());

                        // Add tags before input
                        this.selectedTags.forEach(taskId => {
                            const task = allTasks.find(t => t.id === taskId);
                            if (!task) return;

                            const shortId = task.id.substring(0, 8);
                            // Truncate title to 25 characters
                            const title = task.title.length > 25
                                ? task.title.substring(0, 25) + '...'
                                : task.title;

                            const tag = document.createElement('div');
                            tag.className = 'autocomplete-tag';
                            tag.title = task.title; // Show full title on hover
                            tag.innerHTML = `
                                <span class="autocomplete-tag-id">${escapeHtml(title)}</span>
                                <span class="autocomplete-tag-remove" data-task-id="${taskId}">&times;</span>
                            `;

                            // Insert before input
                            this.containerElement.insertBefore(tag, this.inputElement);

                            // Attach remove handler
                            tag.querySelector('.autocomplete-tag-remove').addEventListener('click', (e) => {
                                e.stopPropagation();
                                const id = e.target.getAttribute('data-task-id');
                                this.removeTag(id);
                            });
                        });
                    }

                    updateHiddenField() {
                        // Calculate additions: tasks in selectedTags but not in originalTags
                        const additions = this.selectedTags.filter(id => !this.originalTags.includes(id));

                        // Calculate removals: tasks in originalTags but not in selectedTags
                        const removals = this.originalTags.filter(id => !this.selectedTags.includes(id));

                        // Update add field (e.g., add_blocks or add_blocked_by)
                        const hiddenField = document.getElementById(this.hiddenFieldId);
                        if (hiddenField) {
                            hiddenField.value = additions.join(',');
                        }

                        // Update remove field (e.g., remove_blocks or remove_blocked_by)
                        if (this.removeFieldId) {
                            const removeField = document.getElementById(this.removeFieldId);
                            if (removeField) {
                                removeField.value = removals.join(',');
                            }
                        }
                    }

                    loadInitialTags(taskIds) {
                        // Load existing dependencies as tags
                        if (!taskIds || !Array.isArray(taskIds)) return;

                        this.originalTags = [...taskIds];
                        this.selectedTags = [...taskIds];
                        this.renderTags();
                        this.updateHiddenField();
                    }

                    reset() {
                        this.originalTags = [];
                        this.selectedTags = [];
                        this.renderTags();
                        this.updateHiddenField();
                        if (this.inputElement) {
                            this.inputElement.value = '';
                        }
                        this.hideDropdown();
                    }

                    setExcludeTaskId(taskId) {
                        this.excludeTaskId = taskId;
                    }
                }

                // Global autocomplete instances
                let createBlockedByAutocomplete = null;
                let editAddBlocksAutocomplete = null;
                let editAddBlockedByAutocomplete = null;

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
                            (task.status === 'open' || task.status === 'blocked') ? `<a href="/api/update?id=${task.id}&status=in_progress">Start</a>` : '',
                            (task.status === 'open' || task.status === 'in_progress' || task.status === 'blocked') ? `<a href="/api/update?id=${task.id}&status=done">Done</a>` : '',
                            task.status === 'done' ? `<a href="/api/update?id=${task.id}&status=open">Re-open</a>` : '',
                            `<a onclick="deleteTask('${task.id}', '${escapeHtml(task.title).replace(/'/g, '\\\'')}')" style="color: #ff4d4f;">Delete</a>`
                        ].filter(a => a).join(' ');

                        list.innerHTML += `
                            <div class="task">
                                <div class="task-id">${task.id.substring(0, 8)}</div>
                                <div class="task-title">${escapeHtml(task.title)}</div>
                                <div class="task-status status-${task.status.replace('_', '-')}">${formatStatus(task.status)}</div>
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

                function formatStatus(status) {
                    // Convert status to display-friendly format
                    return status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                }

                function openCreateModal() {
                    document.getElementById('create-modal').style.display = 'block';

                    // Initialize autocomplete for Blocked By field
                    if (!createBlockedByAutocomplete) {
                        createBlockedByAutocomplete = new AutocompleteInput(
                            'create-blocked-by-autocomplete',
                            'create-blocked-by',
                            null,  // No remove field for creation
                            null   // No exclude task for creation
                        );
                    }

                    // Reset form after autocomplete is initialized
                    document.getElementById('create-form').reset();
                    createBlockedByAutocomplete.reset();
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
                    document.getElementById('edit-log').value = '';

                    // Initialize autocomplete for Blocks field (tasks this blocks)
                    if (!editAddBlocksAutocomplete) {
                        editAddBlocksAutocomplete = new AutocompleteInput(
                            'edit-add-blocks-autocomplete',
                            'edit-add-blocks',
                            'edit-remove-blocks',  // Remove field
                            taskId  // Exclude current task
                        );
                    } else {
                        editAddBlocksAutocomplete.setExcludeTaskId(taskId);
                        editAddBlocksAutocomplete.reset();
                    }
                    // Load existing blocks
                    if (task.blocks && task.blocks.length > 0) {
                        editAddBlocksAutocomplete.loadInitialTags(task.blocks);
                    }

                    // Initialize autocomplete for Blocked By field (tasks that block this)
                    if (!editAddBlockedByAutocomplete) {
                        editAddBlockedByAutocomplete = new AutocompleteInput(
                            'edit-add-blocked-by-autocomplete',
                            'edit-add-blocked-by',
                            'edit-remove-blocked-by',  // Remove field
                            taskId  // Exclude current task
                        );
                    } else {
                        editAddBlockedByAutocomplete.setExcludeTaskId(taskId);
                        editAddBlockedByAutocomplete.reset();
                    }
                    // Load existing blocked_by
                    if (task.blocked_by && task.blocked_by.length > 0) {
                        editAddBlockedByAutocomplete.loadInitialTags(task.blocked_by);
                    }

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
                        logsContainer.innerHTML = '<div class="session-logs">' + logsHtml + '</div>';
                    } else {
                        logsContainer.innerHTML = '<p style="color: var(--color-text-secondary); font-size: 0.875rem;">No session logs yet.</p>';
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
            remove_blocks = get_param('remove_blocks')
            remove_blocked_by = get_param('remove_blocked_by')
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
                    self.remove_blocks = remove_blocks if remove_blocks else None
                    self.remove_blocked_by = remove_blocked_by if remove_blocked_by else None
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
        help="Initialize database and display comprehensive tutorial for AI agents."
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

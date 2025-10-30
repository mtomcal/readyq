#!/usr/bin/env python3

"""
readyq.py: A dependency-free, JSONL-based task tracker with dependency management.
Inspired by Beads AI, but built with only the Python standard library.

Usage:
  ./readyq.py quickstart    - Initialize the .readyq.jsonl file
  ./readyq.py new "My task" - Add a new task
  ./readyq.py list          - List all tasks
  ./readyq.py ready         - List all unblocked, open tasks
  ./readyq.py update <id> [options] - Update a task
  ./readyq.py --web         - Run a simple web UI on http://localhost:8000
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
from urllib.parse import urlparse, parse_qs

# --- Configuration ---

DB_FILE = ".readyq.jsonl"
HOST = "localhost"
PORT = 8000

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
    """
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        for task in tasks:
            f.write(json.dumps(task) + '\n')

def db_append_task(task):
    """Appends a single new task to the JSONL file (for 'new' operations)."""
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
        "status": "open",  # open, in_progress, done, blocked
        "created_at": now,
        "updated_at": now,
        "blocks": [],
        "blocked_by": []
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

    if args.status:
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
                header { background: #fff; border-bottom: 1px solid #ddd; padding: 1rem 2rem; font-size: 1.5rem; font-weight: 600; }
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
                .task-actions a { text-decoration: none; color: #1890ff; margin-left: 1rem; font-size: 0.9em; }
            </style>
        </head>
        <body>
            <header>readyq Tasks</header>
            <main>
                <h2>Ready Tasks</h2>
                <div id="ready-tasks" class="task-list"></div>

                <h2>All Other Tasks</h2>
                <div id="other-tasks" class="task-list"></div>
            </main>
            <script>
                async function loadTasks() {
                    const response = await fetch('/api/tasks');
                    const tasks = await response.json();

                    const readyList = document.getElementById('ready-tasks');
                    const otherList = document.getElementById('other-tasks');
                    readyList.innerHTML = '';
                    otherList.innerHTML = '';

                    // Determine "ready" state client-side
                    const taskMap = new Map(tasks.map(t => [t.id, t]));

                    const getIsReady = (task) => {
                        if (task.status === 'done') return false;
                        if (!task.blocked_by || task.blocked_by.length === 0) return true;
                        return task.blocked_by.every(id => taskMap.get(id)?.status === 'done');
                    };

                    tasks.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

                    tasks.forEach(task => {
                        const isReady = getIsReady(task);
                        const list = isReady ? readyList : otherList;

                        const actions = [
                            task.status !== 'in_progress' ? `<a href="/api/update?id=${task.id}&status=in_progress">Start</a>` : '',
                            task.status !== 'done' ? `<a href="/api/update?id=${task.id}&status=done">Done</a>` : '',
                            task.status === 'done' ? `<a href="/api/update?id=${task.id}&status=open">Re-open</a>` : ''
                        ].join(' ');

                        list.innerHTML += `
                            <div class="task">
                                <div class="task-id">${task.id.substring(0, 8)}</div>
                                <div class="task-title">${task.title}</div>
                                <div class="task-status status-${task.status.replace('_', '-')}">${task.status}</div>
                                <div class="task-actions">${actions}</div>
                            </div>
                        `;
                    });
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
                def __init__(self, id, status):
                    self.id = id
                    self.status = status

            try:
                cmd_update(FakeArgs(id=task_id, status=status))
                # Redirect back to the main page
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            except Exception as e:
                self._send_response(json.dumps({"error": str(e)}), content_type="application/json", status=500)

        else:
            # Fallback for other files (e.g., /favicon.ico)
            self._send_response("Not Found", status=404)

def cmd_web(args):
    """'--web' command: Starts the web server."""

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
    # Special case: check for '--web' flag first, as it's not a sub-command.
    if '--web' in sys.argv:
        cmd_web(None)
        return

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
    parser_update.add_argument("--status", type=str, choices=['open', 'in_progress', 'done', 'blocked'], help="Set a new status.")
    # TODO: Add --add-blocks and --add-blocked-by for full graph editing
    parser_update.set_defaults(func=cmd_update)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

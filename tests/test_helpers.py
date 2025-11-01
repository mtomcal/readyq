"""
Test helper utilities for readyq tests.

Provides base test classes and utility functions for testing readyq.
"""

import os
import sys
import json
import uuid
import datetime
import tempfile
import shutil
import unittest
from pathlib import Path

# Add parent directory to path to import readyq
sys.path.insert(0, str(Path(__file__).parent.parent))
import readyq


class TempReadyQTest(unittest.TestCase):
    """Base test class that provides temporary database setup/teardown."""

    def setUp(self):
        """Create temporary directory and configure readyq to use it."""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, '.readyq.jsonl')

        # Save original DB_FILE and replace with test path
        self.original_db_file = readyq.DB_FILE
        readyq.DB_FILE = self.db_path

    def tearDown(self):
        """Restore original DB_FILE and clean up temporary directory."""
        readyq.DB_FILE = self.original_db_file
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_task_dict(self, title, description="", status="open",
                         blocks=None, blocked_by=None, sessions=None):
        """
        Create a task dictionary with all required fields.

        This is a test helper that mimics what cmd_new() does.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "id": uuid.uuid4().hex,
            "title": title,
            "description": description,
            "status": status,
            "created_at": now,
            "updated_at": now,
            "blocks": blocks or [],
            "blocked_by": blocked_by or [],
            "sessions": sessions or []
        }

    def save_task(self, task):
        """Save a single task to the database (append mode)."""
        readyq.db_append_task(task)
        return task

    def save_tasks(self, tasks):
        """Save multiple tasks to the database (overwrite mode)."""
        readyq.db_save_tasks(tasks)
        return tasks

    def assertDatabaseValid(self):
        """Assert that the database file is valid JSONL format."""
        with open(self.db_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        self.fail(f"Invalid JSON on line {line_num}: {e}")

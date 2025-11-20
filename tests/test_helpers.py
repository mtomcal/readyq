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
        self.db_path = os.path.join(self.test_dir, '.readyq.md')

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

    def create_markdown_task_fixture(self, title, **kwargs):
        """Create standardized markdown task for testing."""
        defaults = {
            'id': 'c4a0b12d3e8f9a015e1b2c3f4d5e6789',
            'title': title,
            'description': f'Description for {title}',
            'status': 'open',
            'created_at': '2025-10-30T15:30:00.000000+00:00',
            'updated_at': '2025-10-30T16:45:00.000000+00:00',
            'blocks': [],
            'blocked_by': [],
            'sessions': []
        }
        defaults.update(kwargs)
        return readyq.generate_markdown_task(defaults)

    def create_markdown_database_fixture(self, tasks):
        """Create complete markdown database for testing."""
        return '\n\n---\n\n'.join(readyq.generate_markdown_task(task) for task in tasks)

    def save_markdown_task(self, markdown_content, filename=None):
        """Save markdown content to file."""
        if filename is None:
            filename = self.db_path.replace('.jsonl', '.md')
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

    def cleanup_test_files(self):
        """Clean up all test database files."""
        for pattern in ['.readyq.jsonl', '.readyq.md', '.readyq.jsonl.backup']:
            file_path = os.path.join(self.test_dir, pattern)
            if os.path.exists(file_path):
                os.remove(file_path)

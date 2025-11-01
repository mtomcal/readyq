"""
Unit tests for readyq database operations.

Tests:
- db_load_tasks()
- db_save_tasks()
- db_append_task()
"""

import json
from tests.test_helpers import TempReadyQTest
import readyq


class TestDatabaseLoad(TempReadyQTest):
    """Test db_load_tasks() function."""

    def test_load_empty_database(self):
        """Test loading when database file doesn't exist."""
        tasks = readyq.db_load_tasks()
        self.assertEqual(tasks, [])

    def test_load_single_task(self):
        """Test loading database with one task."""
        task = self.create_task_dict(title="Single task")
        self.save_task(task)

        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['id'], task['id'])
        self.assertEqual(tasks[0]['title'], "Single task")

    def test_load_multiple_tasks(self):
        """Test loading database with multiple tasks."""
        created_tasks = []
        for i in range(5):
            task = self.create_task_dict(title=f"Task {i}")
            self.save_task(task)
            created_tasks.append(task)

        loaded_tasks = readyq.db_load_tasks()
        self.assertEqual(len(loaded_tasks), 5)
        for i, task in enumerate(loaded_tasks):
            self.assertEqual(task['title'], f"Task {i}")

    def test_load_preserves_all_fields(self):
        """Test that all task fields are preserved during load."""
        task = self.create_task_dict(
            title="Test task",
            description="Detailed description",
            status="in_progress",
            blocks=["abc123"],
            blocked_by=["def456"],
            sessions=[{"timestamp": "2024-01-01T00:00:00Z", "log": "Session note"}]
        )
        self.save_task(task)

        loaded_tasks = readyq.db_load_tasks()
        loaded_task = loaded_tasks[0]

        self.assertEqual(loaded_task['title'], "Test task")
        self.assertEqual(loaded_task['description'], "Detailed description")
        self.assertEqual(loaded_task['status'], "in_progress")
        self.assertEqual(loaded_task['blocks'], ["abc123"])
        self.assertEqual(loaded_task['blocked_by'], ["def456"])
        self.assertEqual(len(loaded_task['sessions']), 1)

    def test_load_skips_malformed_json(self):
        """Test that malformed JSON lines are skipped with warning."""
        # Create file with mix of valid and invalid JSON
        with open(self.db_path, 'w') as f:
            task1 = self.create_task_dict(title="Task 1")
            f.write(json.dumps(task1) + '\n')
            f.write('this is not valid json\n')  # Invalid line
            task2 = self.create_task_dict(title="Task 2")
            f.write(json.dumps(task2) + '\n')

        # Should load only valid tasks and skip invalid line
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['title'], "Task 1")
        self.assertEqual(tasks[1]['title'], "Task 2")


class TestDatabaseSave(TempReadyQTest):
    """Test db_save_tasks() function."""

    def test_save_empty_list(self):
        """Test saving an empty task list."""
        readyq.db_save_tasks([])

        # Database file should be empty
        with open(self.db_path, 'r') as f:
            content = f.read().strip()
            self.assertEqual(content, "")

    def test_save_single_task(self):
        """Test saving a single task."""
        task = self.create_task_dict(title="Test task")
        readyq.db_save_tasks([task])

        # Reload and verify
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['id'], task['id'])
        self.assertEqual(tasks[0]['title'], "Test task")

    def test_save_multiple_tasks(self):
        """Test saving multiple tasks."""
        tasks = [self.create_task_dict(title=f"Task {i}") for i in range(5)]
        readyq.db_save_tasks(tasks)

        # Reload and verify
        loaded_tasks = readyq.db_load_tasks()
        self.assertEqual(len(loaded_tasks), 5)

    def test_save_overwrites_existing_file(self):
        """Test that save completely replaces existing file content."""
        # Create initial tasks
        for i in range(3):
            self.save_task(self.create_task_dict(title=f"Old Task {i}"))

        # Save new set of tasks (overwrite)
        new_tasks = [
            self.create_task_dict(title="New Task A"),
            self.create_task_dict(title="New Task B")
        ]
        readyq.db_save_tasks(new_tasks)

        # Verify old tasks are gone
        loaded_tasks = readyq.db_load_tasks()
        self.assertEqual(len(loaded_tasks), 2)
        self.assertEqual(loaded_tasks[0]['title'], "New Task A")
        self.assertEqual(loaded_tasks[1]['title'], "New Task B")

    def test_save_creates_valid_jsonl(self):
        """Test that saved file is valid JSONL format."""
        tasks = [self.create_task_dict(title=f"Task {i}") for i in range(3)]
        readyq.db_save_tasks(tasks)

        self.assertDatabaseValid()


class TestDatabaseAppend(TempReadyQTest):
    """Test db_append_task() function."""

    def test_append_to_empty_database(self):
        """Test appending to non-existent database file."""
        task = self.create_task_dict(title="First task")
        readyq.db_append_task(task)

        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['title'], "First task")

    def test_append_to_existing_database(self):
        """Test appending to existing database."""
        # Create initial task
        self.save_task(self.create_task_dict(title="Task 1"))

        # Append new task
        new_task = self.create_task_dict(title="Task 2")
        readyq.db_append_task(new_task)

        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['title'], "Task 1")
        self.assertEqual(tasks[1]['title'], "Task 2")

    def test_append_multiple_tasks_sequentially(self):
        """Test appending multiple tasks one at a time."""
        for i in range(5):
            task = self.create_task_dict(title=f"Task {i}")
            readyq.db_append_task(task)

        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 5)

    def test_append_creates_valid_jsonl(self):
        """Test that appended tasks create valid JSONL."""
        for i in range(3):
            task = self.create_task_dict(title=f"Task {i}")
            readyq.db_append_task(task)

        self.assertDatabaseValid()


class TestDatabaseIntegrity(TempReadyQTest):
    """Test database file integrity and special cases."""

    def test_empty_database_file_is_valid(self):
        """Test that empty file is considered valid."""
        # Create empty file
        with open(self.db_path, 'w') as f:
            pass

        tasks = readyq.db_load_tasks()
        self.assertEqual(tasks, [])

    def test_database_with_unicode_content(self):
        """Test that unicode characters are handled correctly."""
        task = self.create_task_dict(title="Task with émojis 🎉 and 中文")
        readyq.db_append_task(task)

        tasks = readyq.db_load_tasks()
        self.assertEqual(tasks[0]['title'], "Task with émojis 🎉 and 中文")

    def test_rapid_sequential_appends(self):
        """Test that rapid sequential appends maintain file integrity."""
        for i in range(20):
            task = self.create_task_dict(title=f"Rapid task {i}")
            readyq.db_append_task(task)

        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 20)
        self.assertDatabaseValid()

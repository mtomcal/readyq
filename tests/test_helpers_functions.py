"""
Unit tests for readyq helper functions.

Tests:
- find_task()
- get_short_id()
- print_task_list()
"""

import io
import sys
from tests.test_helpers import TempReadyQTest
import readyq


class TestFindTask(TempReadyQTest):
    """Test find_task() function."""

    def test_find_task_by_full_id(self):
        """Test finding task using full ID."""
        task = self.create_task_dict(title="Test task")
        self.save_task(task)

        found_task, all_tasks = readyq.find_task(task['id'])
        self.assertIsNotNone(found_task)
        self.assertEqual(found_task['id'], task['id'])

    def test_find_task_by_prefix(self):
        """Test finding task using ID prefix."""
        task = self.create_task_dict(title="Test task")
        self.save_task(task)

        # Use first 8 characters as prefix
        prefix = task['id'][:8]
        found_task, all_tasks = readyq.find_task(prefix)
        self.assertIsNotNone(found_task)
        self.assertEqual(found_task['id'], task['id'])

    def test_find_task_not_found(self):
        """Test finding non-existent task returns None."""
        self.save_task(self.create_task_dict(title="Task"))

        found_task, all_tasks = readyq.find_task("nonexistent")
        self.assertIsNone(found_task)

    def test_find_task_ambiguous_prefix(self):
        """Test that ambiguous prefix returns None."""
        # Create two tasks with IDs starting with same character
        # This is unlikely with UUIDs but we need to test the logic
        task1 = self.create_task_dict(title="Task 1")
        task2 = self.create_task_dict(title="Task 2")

        # Manually set IDs to have same prefix
        task1['id'] = "aaa111"
        task2['id'] = "aaa222"

        self.save_tasks([task1, task2])

        # Search with ambiguous prefix
        found_task, all_tasks = readyq.find_task("aaa")
        self.assertIsNone(found_task)  # Should return None for ambiguity

    def test_find_task_empty_database(self):
        """Test finding task in empty database."""
        found_task, all_tasks = readyq.find_task("anything")
        self.assertIsNone(found_task)
        self.assertEqual(all_tasks, [])

    def test_find_task_returns_all_tasks(self):
        """Test that find_task returns list of all tasks."""
        tasks = [self.create_task_dict(title=f"Task {i}") for i in range(5)]
        self.save_tasks(tasks)

        found_task, all_tasks = readyq.find_task(tasks[0]['id'])
        self.assertEqual(len(all_tasks), 5)


class TestGetShortId(TempReadyQTest):
    """Test get_short_id() function."""

    def test_get_short_id_returns_8_chars(self):
        """Test that short ID is 8 characters."""
        task_id = "abcdef1234567890"
        short_id = readyq.get_short_id(task_id)
        self.assertEqual(len(short_id), 8)

    def test_get_short_id_returns_prefix(self):
        """Test that short ID is prefix of full ID."""
        task_id = "abcdef1234567890"
        short_id = readyq.get_short_id(task_id)
        self.assertEqual(short_id, "abcdef12")

    def test_get_short_id_with_short_input(self):
        """Test get_short_id with ID shorter than 8 chars."""
        task_id = "abc"
        short_id = readyq.get_short_id(task_id)
        self.assertEqual(short_id, "abc")


class TestPrintTaskList(TempReadyQTest):
    """Test print_task_list() function."""

    def test_print_empty_task_list(self):
        """Test printing empty task list."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            readyq.print_task_list([])
            output = captured_output.getvalue()
            self.assertIn("No tasks found", output)
        finally:
            sys.stdout = old_stdout

    def test_print_single_task(self):
        """Test printing single task."""
        task = self.create_task_dict(title="Test task", status="open")

        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            readyq.print_task_list([task])
            output = captured_output.getvalue()

            # Should contain headers and task info
            self.assertIn("ID", output)
            self.assertIn("Status", output)
            self.assertIn("Title", output)
            self.assertIn("Test task", output)
            self.assertIn("open", output)
        finally:
            sys.stdout = old_stdout

    def test_print_multiple_tasks(self):
        """Test printing multiple tasks."""
        tasks = [
            self.create_task_dict(title="Task 1", status="open"),
            self.create_task_dict(title="Task 2", status="done"),
            self.create_task_dict(title="Task 3", status="in_progress")
        ]

        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            readyq.print_task_list(tasks)
            output = captured_output.getvalue()

            # Should contain all tasks
            self.assertIn("Task 1", output)
            self.assertIn("Task 2", output)
            self.assertIn("Task 3", output)
        finally:
            sys.stdout = old_stdout

    def test_print_task_shows_blocked_status(self):
        """Test that print shows whether task is blocked."""
        task_blocked = self.create_task_dict(
            title="Blocked task",
            blocked_by=["other_task_id"]
        )
        task_unblocked = self.create_task_dict(title="Unblocked task")

        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            readyq.print_task_list([task_blocked, task_unblocked])
            output = captured_output.getvalue()

            # Should show blocked status
            self.assertIn("Yes", output)  # For blocked task
            self.assertIn("No", output)   # For unblocked task
        finally:
            sys.stdout = old_stdout

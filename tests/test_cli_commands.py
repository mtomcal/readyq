"""
Integration tests for readyq CLI commands.

Tests CLI commands by calling command functions directly.
"""

import sys
import io
from tests.test_helpers import TempReadyQTest
import readyq


class FakeArgs:
    """Mock args object for testing command functions."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestNewCommand(TempReadyQTest):
    """Test 'new' command."""

    def test_new_basic_task(self):
        """Test creating a basic task with just title."""
        args = FakeArgs(
            title='Test task',
            description=None,
            blocked_by=None
        )

        readyq.cmd_new(args)

        # Verify task was created in database
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['title'], 'Test task')
        self.assertEqual(tasks[0]['status'], 'open')

    def test_new_task_with_description(self):
        """Test creating task with description."""
        args = FakeArgs(
            title='Task title',
            description='Detailed description',
            blocked_by=None
        )

        readyq.cmd_new(args)

        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], 'Detailed description')

    def test_new_task_with_blocker(self):
        """Test creating task blocked by another task."""
        # Create blocker task first
        blocker = self.create_task_dict(title="Blocker task")
        self.save_task(blocker)

        # Create blocked task
        args = FakeArgs(
            title='Blocked task',
            description=None,
            blocked_by=blocker['id'][:8]
        )

        readyq.cmd_new(args)

        # Verify dependency was created
        tasks = readyq.db_load_tasks()
        blocked_task = next(t for t in tasks if t['title'] == 'Blocked task')
        blocker_task = next(t for t in tasks if t['title'] == 'Blocker task')

        self.assertEqual(blocked_task['status'], 'blocked')
        self.assertIn(blocker_task['id'], blocked_task['blocked_by'])
        self.assertIn(blocked_task['id'], blocker_task['blocks'])


class TestListCommand(TempReadyQTest):
    """Test 'list' command."""

    def test_list_empty_database(self):
        """Test listing tasks when database is empty."""
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            args = FakeArgs()
            readyq.cmd_list(args)
            output = captured.getvalue()
            self.assertIn("No tasks found", output)
        finally:
            sys.stdout = old_stdout

    def test_list_single_task(self):
        """Test listing single task."""
        task = self.create_task_dict(title="Test task")
        self.save_task(task)

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            args = FakeArgs()
            readyq.cmd_list(args)
            output = captured.getvalue()

            self.assertIn("Test task", output)
            self.assertIn(task['id'][:8], output)
        finally:
            sys.stdout = old_stdout

    def test_list_multiple_tasks(self):
        """Test listing multiple tasks."""
        tasks = [self.create_task_dict(title=f"Task {i}") for i in range(5)]
        self.save_tasks(tasks)

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            args = FakeArgs()
            readyq.cmd_list(args)
            output = captured.getvalue()

            for i in range(5):
                self.assertIn(f"Task {i}", output)
        finally:
            sys.stdout = old_stdout


class TestReadyCommand(TempReadyQTest):
    """Test 'ready' command."""

    def test_ready_shows_unblocked_tasks(self):
        """Test that ready shows only unblocked tasks."""
        # Create blocker and blocked tasks
        blocker = self.create_task_dict(title="Unblock Task A", status="open")
        blocked = self.create_task_dict(
            title="Waiting Task B",
            status="blocked",
            blocked_by=[blocker['id']]
        )
        blocker['blocks'] = [blocked['id']]

        self.save_tasks([blocker, blocked])

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            args = FakeArgs()
            readyq.cmd_ready(args)
            output = captured.getvalue()

            # Should show blocker task, not blocked task
            self.assertIn("Unblock Task A", output)
            self.assertNotIn("Waiting Task B", output)
        finally:
            sys.stdout = old_stdout

    def test_ready_excludes_done_tasks(self):
        """Test that ready excludes done tasks."""
        open_task = self.create_task_dict(title="Open task", status="open")
        done_task = self.create_task_dict(title="Done task", status="done")

        self.save_tasks([open_task, done_task])

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            args = FakeArgs()
            readyq.cmd_ready(args)
            output = captured.getvalue()

            self.assertIn("Open task", output)
            self.assertNotIn("Done task", output)
        finally:
            sys.stdout = old_stdout


class TestUpdateCommand(TempReadyQTest):
    """Test 'update' command."""

    def test_update_status(self):
        """Test updating task status."""
        task = self.create_task_dict(title="Test task", status="open")
        self.save_task(task)

        args = FakeArgs(
            id=task['id'][:8],
            status='done',
            title=None,
            description=None,
            log=None,
            delete_log=None,
            add_blocks=None,
            add_blocked_by=None,
            remove_blocks=None,
            remove_blocked_by=None
        )

        readyq.cmd_update(args)

        # Verify status changed
        tasks = readyq.db_load_tasks()
        self.assertEqual(tasks[0]['status'], 'done')

    def test_update_title(self):
        """Test updating task title."""
        task = self.create_task_dict(title="Old title")
        self.save_task(task)

        args = FakeArgs(
            id=task['id'][:8],
            title='New title',
            status=None,
            description=None,
            log=None,
            delete_log=None,
            add_blocks=None,
            add_blocked_by=None,
            remove_blocks=None,
            remove_blocked_by=None
        )

        readyq.cmd_update(args)

        tasks = readyq.db_load_tasks()
        self.assertEqual(tasks[0]['title'], 'New title')

    def test_update_add_log(self):
        """Test adding session log to task."""
        task = self.create_task_dict(title="Test task")
        self.save_task(task)

        args = FakeArgs(
            id=task['id'][:8],
            log='Session note',
            status=None,
            title=None,
            description=None,
            delete_log=None,
            add_blocks=None,
            add_blocked_by=None,
            remove_blocks=None,
            remove_blocked_by=None
        )

        readyq.cmd_update(args)

        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks[0]['sessions']), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], 'Session note')


class TestShowCommand(TempReadyQTest):
    """Test 'show' command."""

    def test_show_displays_task_details(self):
        """Test that show displays full task details."""
        task = self.create_task_dict(
            title="Test task",
            description="Detailed description",
            status="in_progress"
        )
        self.save_task(task)

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            args = FakeArgs(id=task['id'][:8])
            readyq.cmd_show(args)
            output = captured.getvalue()

            self.assertIn("Test task", output)
            self.assertIn("Detailed description", output)
            self.assertIn("in_progress", output)
            self.assertIn(task['id'], output)
        finally:
            sys.stdout = old_stdout


class TestDeleteCommand(TempReadyQTest):
    """Test 'delete' command."""

    def test_delete_removes_task(self):
        """Test that delete removes task from database."""
        task = self.create_task_dict(title="Task to delete")
        self.save_task(task)

        args = FakeArgs(id=task['id'][:8])
        readyq.cmd_delete(args)

        # Verify task was deleted
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 0)

    def test_delete_cleans_up_dependencies(self):
        """Test that delete removes task from dependency lists."""
        task1 = self.create_task_dict(title="Task 1")
        task2 = self.create_task_dict(
            title="Task 2",
            blocked_by=[task1['id']]
        )
        task1['blocks'] = [task2['id']]

        self.save_tasks([task1, task2])

        # Delete task1
        args = FakeArgs(id=task1['id'][:8])
        readyq.cmd_delete(args)

        # Verify task2's blocked_by is now empty
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['blocked_by'], [])

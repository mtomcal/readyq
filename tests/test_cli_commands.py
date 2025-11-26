"""
Integration tests for readyq CLI commands.

Tests CLI commands by calling command functions directly.
"""

import sys
import io
import os
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
        tasks = readyq.load_tasks()
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

        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], 'Detailed description')

    def test_new_task_with_multiline_description(self):
        """Test creating task with multiline description."""
        multiline_desc = "Line 1\nLine 2\nLine 3"
        args = FakeArgs(
            title='Multiline task',
            description=multiline_desc,
            blocked_by=None
        )

        readyq.cmd_new(args)

        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], multiline_desc)

    def test_new_task_with_markdown_headers_in_description(self):
        """Test creating task with markdown headers in description."""
        desc_with_headers = "## Section 1\nContent here\n\n### Subsection\nMore content"
        args = FakeArgs(
            title='Task with headers',
            description=desc_with_headers,
            blocked_by=None
        )

        readyq.cmd_new(args)

        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], desc_with_headers)

    def test_new_task_with_horizontal_rules_in_description(self):
        """Test creating task with horizontal rules in description."""
        desc_with_hr = "Before\n---\nAfter"
        args = FakeArgs(
            title='Task with HR',
            description=desc_with_hr,
            blocked_by=None
        )

        readyq.cmd_new(args)

        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], desc_with_hr)

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
        tasks = readyq.load_tasks()
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
        tasks = readyq.load_tasks()
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

        tasks = readyq.load_tasks()
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

        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks[0]['sessions']), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], 'Session note')

    def test_update_add_multiline_log(self):
        """Test adding multiline session log to task."""
        task = self.create_task_dict(title="Test task")
        self.save_task(task)

        multiline_log = "Line 1\nLine 2\nLine 3"
        args = FakeArgs(
            id=task['id'][:8],
            log=multiline_log,
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

        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks[0]['sessions']), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], multiline_log)

    def test_update_add_log_with_markdown_headers(self):
        """Test adding session log with markdown headers."""
        task = self.create_task_dict(title="Test task")
        self.save_task(task)

        log_with_headers = "## Work Done\nImplemented feature X\n\n### Testing\nRan all tests"
        args = FakeArgs(
            id=task['id'][:8],
            log=log_with_headers,
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

        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks[0]['sessions']), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], log_with_headers)

    def test_update_add_log_with_horizontal_rules(self):
        """Test adding session log with horizontal rules."""
        task = self.create_task_dict(title="Test task")
        self.save_task(task)

        log_with_hr = "Before section\n---\nAfter section"
        args = FakeArgs(
            id=task['id'][:8],
            log=log_with_hr,
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

        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks[0]['sessions']), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], log_with_hr)


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
        tasks = readyq.load_tasks()
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
        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['blocked_by'], [])


class TestNewCommandMarkdown(TempReadyQTest):
    """Test 'new' command with markdown database."""

    def test_new_creates_markdown_format(self):
        """Test that new command creates markdown format tasks."""
        # Ensure no existing files
        self.cleanup_test_files()
        
        # Create task via CLI
        args = FakeArgs(
            title="Test Task",
            description="Test Description",
            blocked_by=None
        )
        readyq.cmd_new(args)
        
        # Verify markdown file created
        self.assertTrue(os.path.exists(self.db_path))
        
        # Verify it's markdown format
        with open(self.db_path, 'r') as f:
            content = f.read()
        
        self.assertIn('# Task: Test Task', content)
        self.assertNotIn('{', content)  # Not JSONL

    def test_new_with_existing_jsonl_migrates(self):
        """Test that new command triggers migration if JSONL exists."""
        # Create JSONL file
        task = self.create_task_dict("Existing Task")
        jsonl_path = self.db_path.replace('.md', '.jsonl')
        with open(jsonl_path, 'w') as f:
            f.write(readyq.json.dumps(task) + '\n')
        
        # Create new task
        args = FakeArgs(
            title="New Task",
            description="New Description", 
            blocked_by=None
        )
        readyq.cmd_new(args)
        
        # Verify markdown file created and JSONL backed up
        jsonl_path = self.db_path.replace('.md', '.jsonl')
        backup_path = jsonl_path + '.backup'
        

        
        self.assertTrue(os.path.exists(self.db_path))
        self.assertTrue(os.path.exists(backup_path))
        
        # Verify both tasks exist in markdown
        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks), 2)
        titles = [task['title'] for task in tasks]
        self.assertIn("Existing Task", titles)
        self.assertIn("New Task", titles)


class TestListCommandMarkdown(TempReadyQTest):
    """Test 'list' command with markdown database."""

    def test_list_displays_markdown_tasks(self):
        """Test that list works with markdown format."""
        # Create tasks in markdown
        tasks = [
            self.create_task_dict("Task 1"),
            self.create_task_dict("Task 2")
        ]
        readyq.md_save_tasks(tasks)
        
        # Capture list output
        from io import StringIO
        import sys
        
        captured_output = StringIO()
        sys.stdout = captured_output
        
        args = FakeArgs()
        readyq.cmd_list(args)
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("Task 1", output)
        self.assertIn("Task 2", output)


class TestReadyCommandMarkdown(TempReadyQTest):
    """Test 'ready' command with markdown database."""

    def test_ready_respects_markdown_dependencies(self):
        """Test that ready command respects dependency graph."""
        # Create tasks with dependencies in markdown
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")
        task2['blocked_by'] = [task1['id']]
        
        readyq.md_save_tasks([task1, task2])
        
        # Capture ready output
        from io import StringIO
        import sys
        
        captured_output = StringIO()
        sys.stdout = captured_output
        
        args = FakeArgs()
        readyq.cmd_ready(args)
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Should only show unblocked task
        self.assertIn("Task 1", output)
        self.assertNotIn("Task 2", output)


class TestUpdateCommandMarkdown(TempReadyQTest):
    """Test 'update' command with markdown database."""

    def test_update_modifies_markdown_file(self):
        """Test that update modifies markdown format."""
        # Create task in markdown
        task = self.create_task_dict("Test Task")
        readyq.md_save_tasks([task])
        
        # Update task
        args = FakeArgs(
            id=task['id'][:8],
            status='in_progress',
            log=None,
            delete_log=None,
            title=None,
            description=None,
            add_blocks=None,
            add_blocked_by=None,
            remove_blocks=None,
            remove_blocked_by=None
        )
        readyq.cmd_update(args)
        
        # Verify markdown updated
        tasks = readyq.md_load_tasks()
        self.assertEqual(tasks[0]['status'], 'in_progress')

    def test_update_preserves_markdown_formatting(self):
        """Test that updates preserve markdown in descriptions."""
        # Create task with markdown description
        task = self.create_task_dict("Test Task")
        task['description'] = "**Bold** and *italic* text"
        readyq.md_save_tasks([task])
        
        # Update title
        args = FakeArgs(
            id=task['id'][:8],
            status=None,
            log=None,
            delete_log=None,
            title="Updated Task",
            description=None,
            add_blocks=None,
            add_blocked_by=None,
            remove_blocks=None,
            remove_blocked_by=None
        )
        readyq.cmd_update(args)
        
        # Verify markdown formatting preserved
        tasks = readyq.md_load_tasks()
        self.assertEqual(tasks[0]['title'], "Updated Task")
        self.assertEqual(tasks[0]['description'], "**Bold** and *italic* text")


class TestQuickstartCommand(TempReadyQTest):
    """Test 'quickstart' command."""

    def test_quickstart_creates_empty_file(self):
        """Test quickstart creates empty markdown file when no JSONL exists."""
        # Ensure no database files exist
        self.assertFalse(os.path.exists(self.db_path))
        self.assertFalse(os.path.exists(self.db_path.replace('.md', '.jsonl')))
        
        args = FakeArgs()
        readyq.cmd_quickstart(args)
        
        # Should create empty markdown file
        self.assertTrue(os.path.exists(self.db_path))
        with open(self.db_path, 'r') as f:
            content = f.read()
        self.assertEqual(content.strip(), '')

    def test_quickstart_migrates_from_jsonl(self):
        """Test quickstart migrates existing JSONL file to markdown."""
        import json
        
        # Create test JSONL file with tasks
        jsonl_file = self.db_path.replace('.md', '.jsonl')
        test_tasks = [
            {
                "id": "test1234567890abcdef1234567890abcdef",
                "title": "Test task from JSONL",
                "description": "This task should be migrated",
                "status": "open",
                "created_at": "2025-11-23T10:00:00Z",
                "updated_at": "2025-11-23T10:00:00Z",
                "blocks": [],
                "blocked_by": [],
                "sessions": []
            }
        ]
        
        with open(jsonl_file, 'w') as f:
            for task in test_tasks:
                f.write(json.dumps(task) + '\n')
        
        # Ensure markdown file doesn't exist yet
        self.assertFalse(os.path.exists(self.db_path))
        
        args = FakeArgs()
        readyq.cmd_quickstart(args)
        
        # Should create markdown file with migrated tasks
        self.assertTrue(os.path.exists(self.db_path))
        self.assertTrue(os.path.exists(jsonl_file + '.backup'))  # Backup should be created
        
        # Verify migration worked by loading tasks
        tasks = readyq.load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['title'], 'Test task from JSONL')
        self.assertEqual(tasks[0]['description'], 'This task should be migrated')
        
        # Verify markdown file is not empty
        with open(self.db_path, 'r') as f:
            content = f.read()
        self.assertNotEqual(content.strip(), '')
        self.assertIn('Test task from JSONL', content)

    def test_quickstart_does_not_overwrite_existing_markdown(self):
        """Test quickstart doesn't overwrite existing markdown file."""
        # Create existing markdown file with content
        with open(self.db_path, 'w') as f:
            f.write('# Existing content\n')
        
        # Create JSONL file too
        jsonl_file = self.db_path.replace('.md', '.jsonl')
        with open(jsonl_file, 'w') as f:
            f.write('{"id": "test", "title": "Should not migrate"}\n')
        
        original_content = None
        with open(self.db_path, 'r') as f:
            original_content = f.read()
        
        args = FakeArgs()
        readyq.cmd_quickstart(args)
        
        # Markdown file should not be changed
        with open(self.db_path, 'r') as f:
            current_content = f.read()
        self.assertEqual(current_content, original_content)

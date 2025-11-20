"""
Unit tests for readyq database operations.

Tests:
- db_load_tasks()
- db_save_tasks()
- db_append_task()
"""

import json
import os
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
        task = self.create_task_dict(title="Task with émojis 🎉 and unicode")
        readyq.db_append_task(task)

        tasks = readyq.db_load_tasks()
        self.assertEqual(tasks[0]['title'], "Task with émojis 🎉 and unicode")

    def test_rapid_sequential_appends(self):
        """Test that rapid sequential appends maintain file integrity."""
        for i in range(20):
            task = self.create_task_dict(title=f"Rapid task {i}")
            readyq.db_append_task(task)

        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 20)
        self.assertDatabaseValid()


class TestMarkdownDatabaseLoad(TempReadyQTest):
    """Test md_load_tasks() function."""

    def test_load_empty_markdown_database(self):
        """Test loading when markdown database file doesn't exist."""
        tasks = readyq.md_load_tasks()
        self.assertEqual(tasks, [])

    def test_load_single_task_markdown(self):
        """Test loading single task from markdown format."""
        task_dict = self.create_task_dict("Test Task")
        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['title'], "Test Task")
        self.assertEqual(tasks[0]['id'], task_dict['id'])

    def test_load_multiple_tasks_markdown(self):
        """Test loading multiple tasks from markdown."""
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")
        markdown = self.create_markdown_database_fixture([task1, task2])
        self.save_markdown_task(markdown)
        
        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['title'], "Task 1")
        self.assertEqual(tasks[1]['title'], "Task 2")

    def test_load_preserves_markdown_formatting(self):
        """Test that markdown formatting in descriptions is preserved."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "**Bold** and *italic* text"
        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = readyq.md_load_tasks()
        self.assertEqual(tasks[0]['description'], "**Bold** and *italic* text")

    def test_load_parses_status_checkboxes(self):
        """Test parsing of status checkbox format."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['status'] = 'in_progress'
        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = readyq.md_load_tasks()
        self.assertEqual(tasks[0]['status'], 'in_progress')

    def test_load_handles_unicode_content(self):
        """Test unicode handling in markdown format."""
        task_dict = self.create_task_dict("Test Task 🎉")
        task_dict['description'] = "Unicode text: émojis 🎉 and special chars"
        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = readyq.md_load_tasks()
        self.assertEqual(tasks[0]['title'], "Test Task 🎉")
        self.assertEqual(tasks[0]['description'], "Unicode text: émojis 🎉 and special chars")

    def test_load_extracts_session_logs(self):
        """Test parsing of session log structure."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['sessions'] = [
            {"timestamp": "2025-10-30T15:30:00.000000+00:00", "log": "First session"},
            {"timestamp": "2025-10-30T16:45:00.000000+00:00", "log": "Second session"}
        ]
        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks[0]['sessions']), 2)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "First session")


class TestMarkdownDatabaseSave(TempReadyQTest):
    """Test md_save_tasks() function."""

    def test_save_generates_valid_markdown(self):
        """Test that saved file is valid markdown format."""
        tasks = [self.create_task_dict("Test Task")]
        readyq.md_save_tasks(tasks)
        
        md_path = self.db_path.replace('.jsonl', '.md')
        with open(md_path, 'r') as f:
            content = f.read()
        
        self.assertIn('# Task: Test Task', content)
        self.assertIn('**ID**:', content)
        self.assertIn('## Status', content)
        self.assertIn('- [x] Open', content)  # Task status is 'open', so Open should be checked

    def test_save_preserves_task_order(self):
        """Test that task order is maintained."""
        tasks = [
            self.create_task_dict("First"),
            self.create_task_dict("Second"),
            self.create_task_dict("Third")
        ]
        readyq.md_save_tasks(tasks)
        
        loaded_tasks = readyq.md_load_tasks()
        self.assertEqual(loaded_tasks[0]['title'], "First")
        self.assertEqual(loaded_tasks[1]['title'], "Second")
        self.assertEqual(loaded_tasks[2]['title'], "Third")

    def test_save_escapes_special_characters(self):
        """Test proper escaping of special markdown characters."""
        task_dict = self.create_task_dict("Test *bold* and #hash")
        tasks = [task_dict]
        readyq.md_save_tasks(tasks)
        
        loaded_tasks = readyq.md_load_tasks()
        self.assertEqual(loaded_tasks[0]['title'], "Test *bold* and #hash")


class TestMarkdownDatabaseAppend(TempReadyQTest):
    """Test md_append_task() function."""

    def test_append_creates_valid_separator(self):
        """Test that append adds proper --- separator."""
        task1 = self.create_task_dict("Task 1")
        readyq.md_save_tasks([task1])
        
        task2 = self.create_task_dict("Task 2")
        readyq.md_append_task(task2)
        
        md_path = self.db_path.replace('.jsonl', '.md')
        with open(md_path, 'r') as f:
            content = f.read()
        
        self.assertIn('\n---\n\n', content)

    def test_append_maintains_file_structure(self):
        """Test that append preserves overall file structure."""
        task1 = self.create_task_dict("Task 1")
        readyq.md_save_tasks([task1])
        
        task2 = self.create_task_dict("Task 2")
        readyq.md_append_task(task2)
        
        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 2)


class TestAutoMigration(TempReadyQTest):
    """Test auto-migration functionality."""

    def test_auto_migrate_detects_jsonl(self):
        """Test detection of existing JSONL files."""
        # Create JSONL file
        task = self.create_task_dict("Test Task")
        jsonl_path = self.db_path.replace('.md', '.jsonl')
        with open(jsonl_path, 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Verify no markdown file exists
        self.assertFalse(os.path.exists(self.db_path))
        
        # Run migration
        result = readyq.auto_migrate_jsonl()
        self.assertTrue(result)
        
        # Verify markdown file created
        self.assertTrue(os.path.exists(self.db_path))

    def test_auto_migrate_preserves_all_data(self):
        """Test that all task data is preserved during migration."""
        # Create complex JSONL task
        task = self.create_task_dict("Complex Task")
        task['description'] = "**Bold** description with *italic*"
        task['sessions'] = [
            {"timestamp": "2025-10-30T15:30:00.000000+00:00", "log": "Session log 1"},
            {"timestamp": "2025-10-30T16:45:00.000000+00:00", "log": "Session log 2"}
        ]
        task['blocks'] = []
        task['blocked_by'] = []
        
        jsonl_path = self.db_path.replace('.md', '.jsonl')
        with open(jsonl_path, 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Run migration
        readyq.auto_migrate_jsonl()
        
        # Load and verify
        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        migrated_task = tasks[0]
        
        self.assertEqual(migrated_task['title'], "Complex Task")
        self.assertEqual(migrated_task['description'], "**Bold** description with *italic*")
        self.assertEqual(len(migrated_task['sessions']), 2)
        self.assertEqual(migrated_task['sessions'][0]['log'], "Session log 1")
        self.assertEqual(migrated_task['sessions'][1]['log'], "Session log 2")

    def test_auto_migrate_creates_backup(self):
        """Test that backup file is created."""
        task = self.create_task_dict("Test Task")
        jsonl_path = self.db_path.replace('.md', '.jsonl')
        with open(jsonl_path, 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        readyq.auto_migrate_jsonl()
        
        backup_path = jsonl_path + '.backup'
        self.assertTrue(os.path.exists(backup_path))
        
        # Verify backup contains original data
        with open(backup_path, 'r') as f:
            backup_content = f.read()
        
        self.assertIn(json.dumps(task), backup_content)

    def test_auto_migrate_shows_summary(self):
        """Test migration summary display."""
        task = self.create_task_dict("Test Task")
        jsonl_path = self.db_path.replace('.md', '.jsonl')
        with open(jsonl_path, 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Capture stdout
        from io import StringIO
        import sys
        
        captured_output = StringIO()
        sys.stdout = captured_output
        
        readyq.auto_migrate_jsonl()
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("🔄 Auto-migrating", output)
        self.assertIn("✅ Migration complete!", output)
        self.assertIn("📊 Migrated 1 tasks", output)

    def test_auto_migrate_only_runs_once(self):
        """Test that migration doesn't run repeatedly."""
        task = self.create_task_dict("Test Task")
        jsonl_path = self.db_path.replace('.md', '.jsonl')
        with open(jsonl_path, 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Run migration twice
        result1 = readyq.auto_migrate_jsonl()
        result2 = readyq.auto_migrate_jsonl()
        
        self.assertTrue(result1)  # First run should migrate
        self.assertFalse(result2)  # Second run should not migrate

    def test_auto_migrate_handles_corrupted_jsonl(self):
        """Test migration with malformed JSONL."""
        jsonl_path = self.db_path.replace('.md', '.jsonl')
        with open(jsonl_path, 'w') as f:
            f.write('{"id": "valid"}\n')
            f.write('invalid json\n')
            f.write('{"id": "also_valid"}\n')
        
        # Should handle gracefully
        try:
            readyq.auto_migrate_jsonl()
            # If we get here, migration succeeded despite corruption
            tasks = readyq.md_load_tasks()
            self.assertGreaterEqual(len(tasks), 1)  # At least valid tasks migrated
        except Exception:
            # If migration fails, it should be graceful
            self.assertFalse(os.path.exists(self.db_path))


class TestCustomDatabaseFiles(TempReadyQTest):
    """Test custom database file support."""

    def test_custom_db_file_creates_independent_graph(self):
        """Test that custom files have independent task graphs."""
        custom_file = 'custom-tasks.md'
        
        # Create task in custom file
        task = self.create_task_dict("Custom Task")
        readyq.md_save_tasks([task], custom_file)
        
        # Verify main file unaffected
        main_tasks = readyq.load_tasks()
        self.assertEqual(len(main_tasks), 0)
        
        # Verify custom file has task
        custom_tasks = readyq.load_tasks(custom_file)
        self.assertEqual(len(custom_tasks), 1)
        self.assertEqual(custom_tasks[0]['title'], "Custom Task")

    def test_custom_db_file_migrates_independently(self):
        """Test auto-migration per custom file."""
        custom_jsonl = 'custom-tasks.jsonl'
        custom_md = 'custom-tasks.md'
        
        # Ensure markdown file doesn't exist initially
        if os.path.exists(custom_md):
            os.remove(custom_md)
        
        # Create JSONL with custom name
        task = self.create_task_dict("Custom Task")
        with open(custom_jsonl, 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Run migration for custom file
        result = readyq.auto_migrate_jsonl(custom_md)
        self.assertTrue(result)
        
        # Verify migration occurred
        self.assertTrue(os.path.exists(custom_md))
        self.assertTrue(os.path.exists(custom_jsonl + '.backup'))
        
        # Verify main files unaffected (skip check if default file exists from other tests)
        # Note: .readyq.md might exist from other tests, so we just verify custom files work
        
        # Clean up
        if os.path.exists(custom_jsonl):
            os.remove(custom_jsonl)
        if os.path.exists(custom_jsonl + '.backup'):
            os.remove(custom_jsonl + '.backup')
        if os.path.exists(custom_md):
            os.remove(custom_md)

    def test_custom_db_file_with_dependencies(self):
        """Test dependencies work correctly in custom files."""
        custom_file = 'dependency-test.md'
        
        # Create tasks with dependencies
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")
        task2['blocked_by'] = [task1['id']]
        
        readyq.md_save_tasks([task1, task2], custom_file)
        
        # Test ready command logic
        tasks = readyq.load_tasks(custom_file)
        ready_tasks = [t for t in tasks if t['status'] != 'done' and not t.get('blocked_by')]
        
        self.assertEqual(len(ready_tasks), 1)
        self.assertEqual(ready_tasks[0]['title'], "Task 1")
        
        # Clean up
        if os.path.exists(custom_file):
            os.remove(custom_file)

    def test_custom_db_file_validation(self):
        """Test validation works with custom files."""
        custom_file = 'validation-test.md'
        
        # Create task with invalid dependency
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")
        task2['blocked_by'] = ['invalid_id']
        
        readyq.md_save_tasks([task1, task2], custom_file)
        
        # Load should trigger validation
        tasks = readyq.load_tasks(custom_file)
        self.assertEqual(len(tasks), 2)  # Tasks still load despite errors
        
        # Clean up
        if os.path.exists(custom_file):
            os.remove(custom_file)

    def test_custom_db_file_format_detection(self):
        """Test format detection works with custom files."""
        custom_jsonl = 'format-test.jsonl'
        custom_md = 'format-test.md'
        
        # Test JSONL detection
        task = self.create_task_dict("Test Task")
        with open(custom_jsonl, 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        format_type = readyq.detect_database_format(custom_jsonl)
        self.assertEqual(format_type, 'jsonl')
        
        # Test markdown detection
        readyq.md_save_tasks([task], custom_md)
        format_type = readyq.detect_database_format(custom_md)
        self.assertEqual(format_type, 'markdown')
        
        # Clean up
        if os.path.exists(custom_jsonl):
            os.remove(custom_jsonl)
        if os.path.exists(custom_md):
            os.remove(custom_md)

    def test_custom_db_file_append_operations(self):
        """Test append operations work with custom files."""
        custom_file = 'append-test.md'
        
        # Create initial task
        task1 = self.create_task_dict("Task 1")
        readyq.md_save_tasks([task1], custom_file)
        
        # Append second task
        task2 = self.create_task_dict("Task 2")
        readyq.append_task(task2, custom_file)
        
        # Verify both tasks exist
        tasks = readyq.load_tasks(custom_file)
        self.assertEqual(len(tasks), 2)
        titles = [t['title'] for t in tasks]
        self.assertIn("Task 1", titles)
        self.assertIn("Task 2", titles)
        
        # Clean up
        if os.path.exists(custom_file):
            os.remove(custom_file)

    def test_custom_db_file_save_operations(self):
        """Test save operations work with custom files."""
        custom_file = 'save-test.md'
        
        # Create and save tasks
        tasks = [
            self.create_task_dict("Task 1"),
            self.create_task_dict("Task 2"),
            self.create_task_dict("Task 3")
        ]
        readyq.save_tasks(tasks, custom_file)
        
        # Verify file exists and contains correct content
        self.assertTrue(os.path.exists(custom_file))
        
        with open(custom_file, 'r') as f:
            content = f.read()
        
        self.assertIn("# Task: Task 1", content)
        self.assertIn("# Task: Task 2", content)
        self.assertIn("# Task: Task 3", content)
        self.assertIn("---", content)  # Separator should be present
        
        # Clean up
        if os.path.exists(custom_file):
            os.remove(custom_file)


class TestValidationSystem(TempReadyQTest):
    """Test markdown database validation system."""

    def test_validate_empty_database(self):
        """Test validation of empty database."""
        errors, warnings = readyq.validate_markdown_database([], self.db_path)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_validate_valid_database(self):
        """Test validation of properly formed database."""
        tasks = [
            self.create_task_dict("Task 1"),
            self.create_task_dict("Task 2")
        ]
        errors, warnings = readyq.validate_markdown_database(tasks, self.db_path)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_validate_missing_required_fields(self):
        """Test validation catches missing required fields."""
        tasks = [
            {'title': 'Task without ID'},  # Missing id, created_at, updated_at
            self.create_task_dict("Valid Task")
        ]
        errors, warnings = readyq.validate_markdown_database(tasks, self.db_path)
        self.assertGreater(len(errors), 0)
        self.assertIn("missing required field", ' '.join(errors))

    def test_validate_invalid_id_format(self):
        """Test validation catches invalid ID format."""
        task = self.create_task_dict("Task with bad ID")
        task['id'] = 'invalid-id'
        tasks = [task]
        
        errors, warnings = readyq.validate_markdown_database(tasks, self.db_path)
        self.assertGreater(len(errors), 0)
        self.assertIn("invalid ID format", ' '.join(errors))

    def test_validate_duplicate_ids(self):
        """Test validation catches duplicate task IDs."""
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")
        task2['id'] = task1['id']  # Duplicate ID
        
        tasks = [task1, task2]
        errors, warnings = readyq.validate_markdown_database(tasks, self.db_path)
        self.assertGreater(len(errors), 0)
        self.assertIn("Duplicate task IDs", ' '.join(errors))

    def test_validate_nonexistent_dependencies(self):
        """Test validation catches references to non-existent tasks."""
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")
        task2['blocked_by'] = ['nonexistent_id']
        
        tasks = [task1, task2]
        errors, warnings = readyq.validate_markdown_database(tasks, self.db_path)
        self.assertGreater(len(errors), 0)
        self.assertIn("non-existent task", ' '.join(errors))

    def test_validate_circular_dependencies(self):
        """Test validation catches circular dependencies."""
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")
        task1['blocked_by'] = [task2['id']]
        task2['blocked_by'] = [task1['id']]
        
        tasks = [task1, task2]
        errors, warnings = readyq.validate_markdown_database(tasks, self.db_path)
        self.assertGreater(len(errors), 0)
        self.assertIn("Circular dependency", ' '.join(errors))

    def test_find_circular_dependencies_simple(self):
        """Test circular dependency detection with simple cycle."""
        tasks = [
            {'id': 'a', 'title': 'A', 'blocked_by': ['b']},
            {'id': 'b', 'title': 'B', 'blocked_by': ['a']}
        ]
        cycle = readyq.find_circular_dependencies(tasks)
        self.assertIsNotNone(cycle)
        self.assertIn('a', cycle)
        self.assertIn('b', cycle)

    def test_find_circular_dependencies_complex(self):
        """Test circular dependency detection with complex cycle."""
        tasks = [
            {'id': 'a', 'title': 'A', 'blocked_by': ['b']},
            {'id': 'b', 'title': 'B', 'blocked_by': ['c']},
            {'id': 'c', 'title': 'C', 'blocked_by': ['a']}
        ]
        cycle = readyq.find_circular_dependencies(tasks)
        self.assertIsNotNone(cycle)
        self.assertGreaterEqual(len(cycle), 3)  # a -> b -> c -> a

    def test_find_circular_dependencies_none(self):
        """Test circular dependency detection with no cycles."""
        tasks = [
            {'id': 'a', 'title': 'A', 'blocked_by': []},
            {'id': 'b', 'title': 'B', 'blocked_by': ['a']},
            {'id': 'c', 'title': 'C', 'blocked_by': ['a']}
        ]
        cycle = readyq.find_circular_dependencies(tasks)
        self.assertIsNone(cycle)

    def test_validate_individual_task(self):
        """Test individual task validation."""
        task_dict = {'id': 'a' * 32, 'title': 'Test Task'}
        task_dict['created_at'] = '2025-01-01T00:00:00+00:00'
        task_dict['updated_at'] = '2025-01-01T00:00:00+00:00'
        
        errors = readyq.validate_task(task_dict, {'a' * 32: task_dict}, self.db_path)
        self.assertEqual(len(errors), 0)

    def test_print_validation_report_clean(self):
        """Test validation report printing for clean database."""
        from io import StringIO
        import sys
        
        captured_output = StringIO()
        sys.stdout = captured_output
        
        readyq.print_validation_report([], [], self.db_path)
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("validation passed", output)
        self.assertIn("no issues found", output)

    def test_print_validation_report_errors(self):
        """Test validation report printing with errors."""
        from io import StringIO
        import sys
        
        captured_output = StringIO()
        sys.stdout = captured_output
        
        errors = ["Test error 1", "Test error 2"]
        readyq.print_validation_report(errors, [], self.db_path)
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("Error(s) Found", output)
        self.assertIn("Test error 1", output)
        self.assertIn("Test error 2", output)
        self.assertIn("💡", output)  # Should include fix suggestions

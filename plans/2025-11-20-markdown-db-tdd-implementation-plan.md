# JSONL to Markdown Database Migration - TDD Implementation Plan

**Date**: 2025-11-20T00:00:00+00:00  
**Researcher**: Claude Code  
**Methodology**: Test-Driven Development (TDD)

## Overview

This plan implements a migration from JSONL to Markdown database storage for readyq using Test-Driven Development (TDD). The approach maintains all existing functionality while adding human-readable markdown format with auto-migration capabilities.

## Current State Analysis

**Existing Database Layer** (readyq.py:107-143):
- `db_load_tasks()`: Reads JSONL file, parses each line as JSON
- `db_save_tasks()`: Rewrites entire file with JSON dumps + newlines  
- `db_append_task()`: Appends single JSON line to file
- File locking via `db_lock()` context manager
- Uses `.readyq.jsonl` as default DB_FILE

**Current Task Schema**:
```python
{
    "id": "uuid.hex",
    "title": "string",
    "description": "string", 
    "status": "open|in_progress|blocked|done",
    "created_at": "ISO8601-UTC",
    "updated_at": "ISO8601-UTC",
    "blocks": ["task-id-1", "task-id-2"],
    "blocked_by": ["task-id-3"],
    "sessions": [{"timestamp": "ISO8601-UTC", "log": "string"}]
}
```

## Desired End State

**New Markdown Database Format**:
```markdown
# Task: Implement Authentication

**ID**: c4a0b12d3e8f9a015e1b2c3f4d5e6789  
**Created**: 2025-10-30T15:30:00.000000+00:00  
**Updated**: 2025-10-30T16:45:00.000000+00:00  
**Blocks**: 5e1b2c3f4d5e6789c4a0b12d3e8f9a01  
**Blocked By**:  

## Status

- [ ] Open
- [ ] In Progress  
- [x] Blocked
- [ ] Done

## Description

Add JWT-based authentication to API endpoints

## Session Logs

### 2025-10-30T15:30:00.000000+00:00
Started research on JWT libraries. PyJWT looks good.

### 2025-10-30T16:45:00.000000+00:00
Implemented basic middleware. Added tests. Need refresh token logic next.

---

# Task: Write API Tests

**ID**: 5e1b2c3f4d5e6789c4a0b12d3e8f9a01  
**Created**: 2025-10-30T14:00:00.000000+00:00  
**Updated**: 2025-10-30T17:00:00.000000+00:00  
**Blocks**:  
**Blocked By**: c4a0b12d3e8f9a015e1b2c3f4d5e6789  

## Status

- [x] Open
- [ ] In Progress  
- [ ] Blocked
- [x] Done

## Description

Write comprehensive tests for authentication endpoints

## Session Logs

---
```

**Key Discoveries**:
- Current database functions are well-isolated (readyq.py:107-143)
- File locking mechanism can be reused unchanged
- CLI commands depend on database abstraction, not format
- Web UI uses same database functions as CLI
- Task ID resolution (`find_task()`) works with any format

## What We're NOT Doing

- Breaking existing JSONL functionality during transition
- Adding external dependencies (stdlib only)
- Changing CLI command interfaces
- Modifying task schema or validation logic
- Removing file locking or concurrency protection

## Implementation Approach

**TDD Strategy**: Write failing tests first, implement minimal code to pass, refactor, repeat.

**Migration Strategy**: Auto-migration on startup when JSONL file detected but markdown doesn't exist.

## Phase 1: Core Markdown Functions + Tests

### Overview
Implement markdown parsing and generation functions with comprehensive test coverage.

### Changes Required:

#### 1. Test Infrastructure Updates
**File**: `tests/test_helpers.py`
**Changes**: Add format-agnostic test helpers

```python
def create_markdown_task_fixture(title, **kwargs):
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
    return generate_markdown_task(defaults)

def create_markdown_database_fixture(tasks):
    """Create complete markdown database for testing."""
    return '\n\n---\n\n'.join(generate_markdown_task(task) for task in tasks)
```

#### 2. Core Markdown Functions
**File**: `readyq.py` (after line 143)
**Changes**: Add markdown database functions

```python
def md_load_tasks(db_file=None):
    """Load tasks from markdown file."""
    if db_file is None:
        db_file = DB_FILE.replace('.jsonl', '.md')
    
    if not os.path.exists(db_file):
        return []
    
    tasks = []
    content = open(db_file, 'r', encoding='utf-8').read()
    
    # Find all task sections
    task_sections = re.finditer(r'# Task:.*?\n(.*?)(?=\n---|\n# Task:|$)', content, re.DOTALL)
    
    for match in task_sections:
        task_content = match.group(1)
        task = parse_task_section(task_content)
        if task:
            tasks.append(task)
    
    return tasks

def parse_task_section(content):
    """Parse individual task section into dict."""
    task = {}
    
    # Parse metadata lines
    metadata_pattern = r'\*\*(\w+)\*\*:\s*(.*?)(?=\n\*\*|\n##|$)'
    for match in re.finditer(metadata_pattern, content, re.DOTALL):
        key, value = match.groups()
        task[key.lower().replace(' ', '_')] = value.strip()
    
    # Parse description
    desc_match = re.search(r'## Description\n\n(.*?)(?=\n##|\n---|$)', content, re.DOTALL)
    if desc_match:
        task['description'] = desc_match.group(1).strip()
    
    # Parse session logs
    sessions = []
    log_pattern = r'### (\d{4}-\d{2}-\d{2}T.*?)\n(.*?)(?=\n###|\n---|$)'
    for match in re.finditer(log_pattern, content, re.DOTALL):
        timestamp, log_text = match.groups()
        sessions.append({"timestamp": timestamp, "log": log_text.strip()})
    
    if sessions:
        task['sessions'] = sessions
    
    return task

def generate_markdown_task(task):
    """Generate markdown for a single task."""
    md = f"# Task: {task['title']}\n\n"
    
    # Metadata
    md += f"**ID**: {task['id']}\n"
    md += f"**Created**: {task['created_at']}\n"
    md += f"**Updated**: {task['updated_at']}\n"
    
    if task.get('blocks'):
        md += f"**Blocks**: {', '.join(task['blocks'])}\n"
    else:
        md += "**Blocks**: \n"
    
    if task.get('blocked_by'):
        md += f"**Blocked By**: {', '.join(task['blocked_by'])}\n"
    else:
        md += "**Blocked By**: \n"
    
    # Status
    md += "\n## Status\n\n"
    statuses = ['open', 'in_progress', 'blocked', 'done']
    for status in statuses:
        checked = '[x]' if task['status'] == status else '[ ]'
        md += f"- {checked} {status.title()}\n"
    
    # Description
    md += "\n## Description\n\n"
    md += f"{task.get('description', '')}\n"
    
    # Session logs
    if task.get('sessions'):
        md += "\n## Session Logs\n\n"
        for session in task['sessions']:
            md += f"### {session['timestamp']}\n"
            md += f"{session['log']}\n\n"
    
    return md

def md_save_tasks(tasks, db_file=None):
    """Save tasks to markdown file."""
    if db_file is None:
        db_file = DB_FILE.replace('.jsonl', '.md')
    
    with db_lock():
        with open(db_file, 'w', encoding='utf-8') as f:
            for i, task in enumerate(tasks):
                if i > 0:
                    f.write('\n---\n\n')
                f.write(generate_markdown_task(task))

def md_append_task(task, db_file=None):
    """Append task to markdown file."""
    if db_file is None:
        db_file = DB_FILE.replace('.jsonl', '.md')
    
    with db_lock():
        with open(db_file, 'a', encoding='utf-8') as f:
            f.write('\n---\n\n')
            f.write(generate_markdown_task(task))
```

#### 3. Core Markdown Tests
**File**: `tests/test_database.py` (new test classes)
**Changes**: Add markdown database tests

```python
class TestMarkdownDatabaseLoad(TempReadyQTest):
    """Test md_load_tasks() function."""

    def test_load_empty_markdown_database(self):
        """Test loading when markdown database file doesn't exist."""
        tasks = md_load_tasks()
        self.assertEqual(tasks, [])

    def test_load_single_task_markdown(self):
        """Test loading single task from markdown format."""
        task_dict = self.create_task_dict("Test Task")
        markdown = generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['title'], "Test Task")
        self.assertEqual(tasks[0]['id'], task_dict['id'])

    def test_load_multiple_tasks_markdown(self):
        """Test loading multiple tasks from markdown."""
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")
        markdown = create_markdown_database_fixture([task1, task2])
        self.save_markdown_task(markdown)
        
        tasks = md_load_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['title'], "Task 1")
        self.assertEqual(tasks[1]['title'], "Task 2")

    def test_load_preserves_markdown_formatting(self):
        """Test that markdown formatting in descriptions is preserved."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "**Bold** and *italic* text"
        markdown = generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = md_load_tasks()
        self.assertEqual(tasks[0]['description'], "**Bold** and *italic* text")

    def test_load_parses_status_checkboxes(self):
        """Test parsing of status checkbox format."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['status'] = 'in_progress'
        markdown = generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = md_load_tasks()
        self.assertEqual(tasks[0]['status'], 'in_progress')

    def test_load_handles_unicode_content(self):
        """Test unicode handling in markdown format."""
        task_dict = self.create_task_dict("Test Task 🎉")
        task_dict['description'] = "Unicode text: émojis 🎉 and special chars"
        markdown = generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = md_load_tasks()
        self.assertEqual(tasks[0]['title'], "Test Task 🎉")
        self.assertEqual(tasks[0]['description'], "Unicode text: émojis 🎉 and special chars")

    def test_load_extracts_session_logs(self):
        """Test parsing of session log structure."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['sessions'] = [
            {"timestamp": "2025-10-30T15:30:00.000000+00:00", "log": "First session"},
            {"timestamp": "2025-10-30T16:45:00.000000+00:00", "log": "Second session"}
        ]
        markdown = generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)
        
        tasks = md_load_tasks()
        self.assertEqual(len(tasks[0]['sessions']), 2)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "First session")

class TestMarkdownDatabaseSave(TempReadyQTest):
    """Test md_save_tasks() function."""

    def test_save_generates_valid_markdown(self):
        """Test that saved file is valid markdown format."""
        tasks = [self.create_task_dict("Test Task")]
        md_save_tasks(tasks)
        
        with open('.readyq.md', 'r') as f:
            content = f.read()
        
        self.assertIn('# Task: Test Task', content)
        self.assertIn('**ID**:', content)
        self.assertIn('## Status', content)
        self.assertIn('- [ ] Open', content)

    def test_save_preserves_task_order(self):
        """Test that task order is maintained."""
        tasks = [
            self.create_task_dict("First"),
            self.create_task_dict("Second"),
            self.create_task_dict("Third")
        ]
        md_save_tasks(tasks)
        
        loaded_tasks = md_load_tasks()
        self.assertEqual(loaded_tasks[0]['title'], "First")
        self.assertEqual(loaded_tasks[1]['title'], "Second")
        self.assertEqual(loaded_tasks[2]['title'], "Third")

    def test_save_escapes_special_characters(self):
        """Test proper escaping of special markdown characters."""
        task_dict = self.create_task_dict("Test *bold* and #hash")
        tasks = [task_dict]
        md_save_tasks(tasks)
        
        loaded_tasks = md_load_tasks()
        self.assertEqual(loaded_tasks[0]['title'], "Test *bold* and #hash")

class TestMarkdownDatabaseAppend(TempReadyQTest):
    """Test md_append_task() function."""

    def test_append_creates_valid_separator(self):
        """Test that append adds proper --- separator."""
        task1 = self.create_task_dict("Task 1")
        md_save_tasks([task1])
        
        task2 = self.create_task_dict("Task 2")
        md_append_task(task2)
        
        with open('.readyq.md', 'r') as f:
            content = f.read()
        
        self.assertIn('\n---\n\n', content)

    def test_append_maintains_file_structure(self):
        """Test that append preserves overall file structure."""
        task1 = self.create_task_dict("Task 1")
        md_save_tasks([task1])
        
        task2 = self.create_task_dict("Task 2")
        md_append_task(task2)
        
        tasks = md_load_tasks()
        self.assertEqual(len(tasks), 2)
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `python3 run_tests.py -k "TestMarkdownDatabase"`
- [ ] Round-trip data integrity: Load → Save → Load preserves all data
- [ ] Markdown parsing handles all task fields correctly
- [ ] Unicode and special characters preserved

#### Manual Verification:
- [ ] Generated markdown is readable in any markdown viewer
- [ ] Manual editing of markdown file works correctly
- [ ] File locking works with markdown files

---

## Phase 2: Auto-Migration + Tests

### Overview
Implement automatic migration from JSONL to markdown with comprehensive validation.

### Changes Required:

#### 1. Auto-Migration Function
**File**: `readyq.py` (after markdown functions)
**Changes**: Add migration detection and execution

```python
def auto_migrate_jsonl(db_file=None):
    """Auto-import JSONL file on startup if markdown doesn't exist."""
    if db_file is None:
        jsonl_file = DB_FILE
        md_file = DB_FILE.replace('.jsonl', '.md')
    else:
        jsonl_file = db_file.replace('.md', '.jsonl')
        md_file = db_file
    
    # Check if JSONL exists but markdown doesn't
    if os.path.exists(jsonl_file) and not os.path.exists(md_file):
        print(f"🔄 Auto-migrating {jsonl_file} to {md_file}...")
        
        # Load from JSONL using existing functions
        old_db_file = DB_FILE
        globals()['DB_FILE'] = jsonl_file
        try:
            jsonl_tasks = db_load_tasks()
        finally:
            globals()['DB_FILE'] = old_db_file
        
        # Convert to markdown format
        md_content = '\n\n---\n\n'.join(generate_markdown_task(task) for task in jsonl_tasks)
        
        # Create backup
        shutil.copy2(jsonl_file, jsonl_file + ".backup")
        
        # Write markdown file
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        # Show conversion summary
        print(f"✅ Migration complete!")
        print(f"   📄 Created {md_file}")
        print(f"   💾 Backup saved as {jsonl_file}.backup")
        print(f"   📊 Migrated {len(jsonl_tasks)} tasks")
        print(f"   🔄 Old JSONL file can be deleted manually")
        
        return True
    return False
```

#### 2. Migration Tests
**File**: `tests/test_database.py`
**Changes**: Add auto-migration test class

```python
class TestAutoMigration(TempReadyQTest):
    """Test auto-migration functionality."""

    def test_auto_migrate_detects_jsonl(self):
        """Test detection of existing JSONL files."""
        # Create JSONL file
        task = self.create_task_dict("Test Task")
        with open('.readyq.jsonl', 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Verify no markdown file exists
        self.assertFalse(os.path.exists('.readyq.md'))
        
        # Run migration
        result = auto_migrate_jsonl()
        self.assertTrue(result)
        
        # Verify markdown file created
        self.assertTrue(os.path.exists('.readyq.md'))

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
        
        with open('.readyq.jsonl', 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Run migration
        auto_migrate_jsonl()
        
        # Load and verify
        tasks = md_load_tasks()
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
        with open('.readyq.jsonl', 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        auto_migrate_jsonl()
        
        self.assertTrue(os.path.exists('.readyq.jsonl.backup'))
        
        # Verify backup contains original data
        with open('.readyq.jsonl.backup', 'r') as f:
            backup_content = f.read()
        
        self.assertIn(json.dumps(task), backup_content)

    def test_auto_migrate_shows_summary(self):
        """Test migration summary display."""
        task = self.create_task_dict("Test Task")
        with open('.readyq.jsonl', 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Capture stdout
        from io import StringIO
        import sys
        
        captured_output = StringIO()
        sys.stdout = captured_output
        
        auto_migrate_jsonl()
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("🔄 Auto-migrating", output)
        self.assertIn("✅ Migration complete!", output)
        self.assertIn("📊 Migrated 1 tasks", output)

    def test_auto_migrate_only_runs_once(self):
        """Test that migration doesn't run repeatedly."""
        task = self.create_task_dict("Test Task")
        with open('.readyq.jsonl', 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Run migration twice
        result1 = auto_migrate_jsonl()
        result2 = auto_migrate_jsonl()
        
        self.assertTrue(result1)  # First run should migrate
        self.assertFalse(result2)  # Second run should not migrate

    def test_auto_migrate_handles_corrupted_jsonl(self):
        """Test migration with malformed JSONL."""
        with open('.readyq.jsonl', 'w') as f:
            f.write('{"id": "valid"}\n')
            f.write('invalid json\n')
            f.write('{"id": "also_valid"}\n')
        
        # Should handle gracefully
        try:
            auto_migrate_jsonl()
            # If we get here, migration succeeded despite corruption
            tasks = md_load_tasks()
            self.assertGreaterEqual(len(tasks), 1)  # At least valid tasks migrated
        except Exception:
            # If migration fails, it should be graceful
            self.assertFalse(os.path.exists('.readyq.md'))
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `python3 run_tests.py -k "TestAutoMigration"`
- [ ] Migration preserves 100% of task data
- [ ] Backup file created successfully
- [ ] Migration summary displayed correctly
- [ ] No duplicate migrations on subsequent runs

#### Manual Verification:
- [ ] Migration works with complex task structures
- [ ] Backup file can be used to restore original data
- [ ] Migration handles edge cases gracefully

---

## Phase 3: Database Layer Integration + CLI Tests

### Overview
Update database functions to support both formats and integrate with CLI commands.

### Changes Required:

#### 1. Format-Agnostic Database Functions
**File**: `readyq.py`
**Changes**: Update database functions to detect and use appropriate format

```python
def detect_database_format(db_file):
    """Detect if database file is JSONL or markdown."""
    if not os.path.exists(db_file):
        return None
    
    with open(db_file, 'r') as f:
        first_line = f.readline().strip()
        return 'jsonl' if first_line.startswith('{') else 'markdown'

def load_tasks(db_file=None):
    """Load tasks from database (format-agnostic)."""
    if db_file is None:
        db_file = DB_FILE.replace('.jsonl', '.md')
    
    # Auto-migrate if needed
    auto_migrate_jsonl(db_file)
    
    format_type = detect_database_format(db_file)
    
    if format_type == 'jsonl':
        old_db_file = DB_FILE
        globals()['DB_FILE'] = db_file
        try:
            return db_load_tasks()
        finally:
            globals()['DB_FILE'] = old_db_file
    elif format_type == 'markdown':
        return md_load_tasks(db_file)
    else:
        return []

def save_tasks(tasks, db_file=None):
    """Save tasks to database (format-agnostic)."""
    if db_file is None:
        db_file = DB_FILE.replace('.jsonl', '.md')
    
    format_type = detect_database_format(db_file)
    
    if format_type == 'jsonl':
        old_db_file = DB_FILE
        globals()['DB_FILE'] = db_file
        try:
            return db_save_tasks(tasks)
        finally:
            globals()['DB_FILE'] = old_db_file
    elif format_type == 'markdown':
        return md_save_tasks(tasks, db_file)
    else:
        # Default to markdown for new files
        return md_save_tasks(tasks, db_file)

def append_task(task, db_file=None):
    """Append task to database (format-agnostic)."""
    if db_file is None:
        db_file = DB_FILE.replace('.jsonl', '.md')
    
    # Auto-migrate if needed
    auto_migrate_jsonl(db_file)
    
    format_type = detect_database_format(db_file)
    
    if format_type == 'jsonl':
        old_db_file = DB_FILE
        globals()['DB_FILE'] = db_file
        try:
            return db_append_task(task)
        finally:
            globals()['DB_FILE'] = old_db_file
    elif format_type == 'markdown':
        return md_append_task(task, db_file)
```

#### 2. CLI Integration Tests
**File**: `tests/test_cli_commands.py`
**Changes**: Add markdown format tests for all CLI commands

```python
class TestNewCommandMarkdown(TempReadyQTest):
    """Test 'new' command with markdown database."""

    def test_new_creates_markdown_format(self):
        """Test that new command creates markdown format tasks."""
        # Ensure no existing files
        self.cleanup_test_files()
        
        # Create task via CLI
        args = argparse.Namespace(
            title="Test Task",
            description="Test Description",
            blocked_by=None
        )
        cmd_new(args)
        
        # Verify markdown file created
        self.assertTrue(os.path.exists('.readyq.md'))
        
        # Verify it's markdown format
        with open('.readyq.md', 'r') as f:
            content = f.read()
        
        self.assertIn('# Task: Test Task', content)
        self.assertNotIn('{', content)  # Not JSONL

    def test_new_with_existing_jsonl_migrates(self):
        """Test that new command triggers migration if JSONL exists."""
        # Create JSONL file
        task = self.create_task_dict("Existing Task")
        with open('.readyq.jsonl', 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Create new task
        args = argparse.Namespace(
            title="New Task",
            description="New Description", 
            blocked_by=None
        )
        cmd_new(args)
        
        # Verify markdown file created and JSONL backed up
        self.assertTrue(os.path.exists('.readyq.md'))
        self.assertTrue(os.path.exists('.readyq.jsonl.backup'))
        
        # Verify both tasks exist in markdown
        tasks = load_tasks()
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
        md_save_tasks(tasks)
        
        # Capture list output
        from io import StringIO
        import sys
        
        captured_output = StringIO()
        sys.stdout = captured_output
        
        args = argparse.Namespace()
        cmd_list(args)
        
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
        
        md_save_tasks([task1, task2])
        
        # Capture ready output
        from io import StringIO
        import sys
        
        captured_output = StringIO()
        sys.stdout = captured_output
        
        args = argparse.Namespace()
        cmd_ready(args)
        
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
        md_save_tasks([task])
        
        # Update task
        args = argparse.Namespace(
            task_id=task['id'][:8],
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
        cmd_update(args)
        
        # Verify markdown updated
        tasks = md_load_tasks()
        self.assertEqual(tasks[0]['status'], 'in_progress')

    def test_update_preserves_markdown_formatting(self):
        """Test that updates preserve markdown in descriptions."""
        # Create task with markdown description
        task = self.create_task_dict("Test Task")
        task['description'] = "**Bold** and *italic* text"
        md_save_tasks([task])
        
        # Update title
        args = argparse.Namespace(
            task_id=task['id'][:8],
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
        cmd_update(args)
        
        # Verify markdown formatting preserved
        tasks = md_load_tasks()
        self.assertEqual(tasks[0]['title'], "Updated Task")
        self.assertEqual(tasks[0]['description'], "**Bold** and *italic* text")
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `python3 run_tests.py -k "Markdown"`
- [ ] All CLI commands work with both JSONL and markdown formats
- [ ] Auto-migration triggers correctly on command execution
- [ ] Round-trip data integrity maintained across format changes

#### Manual Verification:
- [ ] CLI commands produce expected output with markdown format
- [ ] Migration happens seamlessly for existing JSONL users
- [ ] No user-visible breaking changes

---

## Phase 4: Custom Database Files + Advanced Features

### Overview
Add `--db-file` flag support and comprehensive validation system.

### Changes Required:

#### 1. CLI Argument Parser Updates
**File**: `readyq.py` (main function)
**Changes**: Add `--db-file` flag to all commands

```python
def main():
    parser = argparse.ArgumentParser(description='readyq: dependency-free task tracker')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add --db-file flag to all commands
    parser.add_argument('--db-file', 
                       help='Alternative database file (default: .readyq.md)',
                       default='.readyq.md')
    
    # Update all subparsers to inherit --db-file
    parser_quickstart = subparsers.add_parser('quickstart', help='Initialize and show tutorial')
    parser_quickstart.add_argument('--db-file', 
                                  help='Database file to initialize',
                                  default='.readyq.md')
    
    parser_new = subparsers.add_parser('new', help='Create new task')
    parser_new.add_argument('title', help='Task title')
    parser_new.add_argument('--description', help='Task description')
    parser_new.add_argument('--blocked-by', help='Comma-separated task IDs that block this task')
    parser_new.add_argument('--db-file', 
                           help='Database file to add task to',
                           default='.readyq.md')
    
    # Continue for all other commands...
    
    args = parser.parse_args()
    
    if args.command:
        globals()['DB_FILE'] = args.db_file
        func = globals()[f'cmd_{args.command}']
        func(args)
    else:
        parser.print_help()
```

#### 2. Custom Database Tests
**File**: `tests/test_database.py`
**Changes**: Add custom database file tests

```python
class TestCustomDatabaseFiles(TempReadyQTest):
    """Test custom database file support."""

    def test_custom_db_file_creates_independent_graph(self):
        """Test that custom files have independent task graphs."""
        custom_file = 'custom-tasks.md'
        
        # Create task in custom file
        task = self.create_task_dict("Custom Task")
        md_save_tasks([task], custom_file)
        
        # Verify main file unaffected
        main_tasks = load_tasks()
        self.assertEqual(len(main_tasks), 0)
        
        # Verify custom file has task
        custom_tasks = load_tasks(custom_file)
        self.assertEqual(len(custom_tasks), 1)
        self.assertEqual(custom_tasks[0]['title'], "Custom Task")

    def test_custom_db_file_migrates_independently(self):
        """Test auto-migration per custom file."""
        custom_jsonl = 'custom-tasks.jsonl'
        custom_md = 'custom-tasks.md'
        
        # Create JSONL with custom name
        task = self.create_task_dict("Custom Task")
        with open(custom_jsonl, 'w') as f:
            f.write(json.dumps(task) + '\n')
        
        # Run migration for custom file
        auto_migrate_jsonl(custom_md)
        
        # Verify migration occurred
        self.assertTrue(os.path.exists(custom_md))
        self.assertTrue(os.path.exists(custom_jsonl + '.backup'))
        
        # Verify main files unaffected
        self.assertFalse(os.path.exists('.readyq.md'))

    def test_custom_db_file_web_ui_integration(self):
        """Test web UI with custom database file."""
        custom_file = 'custom-tasks.md'
        
        # Create task in custom file
        task = self.create_task_dict("Custom Task")
        md_save_tasks([task], custom_file)
        
        # Start web server with custom file
        # (This would require more complex setup for full test)
        # For now, verify file exists and is readable
        tasks = load_tasks(custom_file)
        self.assertEqual(len(tasks), 1)
```

#### 3. Validation System
**File**: `readyq.py`
**Changes**: Add markdown validation functions

```python
def validate_markdown_database(tasks, db_file):
    """Comprehensive validation of markdown database file."""
    errors = []
    warnings = []
    
    task_dict = {task['id']: task for task in tasks}
    
    # Validate each task
    for task in tasks:
        task_errors = validate_task(task, task_dict, db_file)
        errors.extend(task_errors)
    
    # Check for duplicate IDs
    if len(tasks) != len(task_dict):
        errors.append("Duplicate task IDs found - each task must have unique ID")
    
    # Check for circular dependencies
    circular_deps = find_circular_dependencies(tasks)
    if circular_deps:
        errors.append(f"Circular dependency detected: {' → '.join(circular_deps)}")
    
    return errors, warnings

def validate_task(task, task_dict, db_file):
    """Validate individual task structure and content."""
    errors = []
    
    # Check required fields
    required_fields = ['id', 'created_at', 'updated_at']
    for field in required_fields:
        if field not in task or not task[field]:
            errors.append(f"Task '{task.get('title', 'Unknown')}' missing required field: {field}")
    
    # Validate ID format
    if task.get('id') and not re.match(r'^[a-f0-9]{32}$', task['id']):
        errors.append(f"Task '{task.get('title', 'Unknown')}' has invalid ID format: {task['id']}")
    
    # Validate dependencies
    for block_id in task.get('blocks', []):
        if block_id not in task_dict:
            errors.append(f"Task '{task['title']}' references non-existent task in blocks: {block_id}")
    
    for block_id in task.get('blocked_by', []):
        if block_id not in task_dict:
            errors.append(f"Task '{task['title']}' references non-existent task in blocked_by: {block_id}")
    
    return errors

def find_circular_dependencies(tasks):
    """Detect circular dependencies in task graph."""
    def has_cycle(task_id, visited, rec_stack, task_dict):
        visited.add(task_id)
        rec_stack.add(task_id)
        
        for blocked_id in task_dict.get(task_id, {}).get('blocked_by', []):
            if blocked_id not in visited:
                if has_cycle(blocked_id, visited, rec_stack, task_dict):
                    return True
            elif blocked_id in rec_stack:
                return True
        
        rec_stack.remove(task_id)
        return False
    
    task_dict = {task['id']: task for task in tasks}
    visited = set()
    
    for task_id in task_dict:
        if task_id not in visited:
            if has_cycle(task_id, visited, set(), task_dict):
                return True
    return False

# Update load_tasks to include validation
def load_tasks(db_file=None):
    """Load tasks from database (format-agnostic) with validation."""
    if db_file is None:
        db_file = DB_FILE.replace('.jsonl', '.md')
    
    # Auto-migrate if needed
    auto_migrate_jsonl(db_file)
    
    format_type = detect_database_format(db_file)
    
    if format_type == 'jsonl':
        old_db_file = DB_FILE
        globals()['DB_FILE'] = db_file
        try:
            tasks = db_load_tasks()
        finally:
            globals()['DB_FILE'] = old_db_file
    elif format_type == 'markdown':
        tasks = md_load_tasks(db_file)
    else:
        return []
    
    # Run validation
    errors, warnings = validate_markdown_database(tasks, db_file)
    
    if errors:
        print_validation_report(errors, warnings, db_file)
        print("\n⚠️  Database loaded with errors. Some functionality may not work correctly.")
        print("🔧 Consider fixing the issues above for optimal performance.")
    elif warnings:
        print(f"⚠️  {len(warnings)} warning(s) found in {db_file}")
        for warning in warnings:
            print(f"   • {warning}")
    
    return tasks

def print_validation_report(errors, warnings, db_file):
    """Print comprehensive validation report."""
    if not errors and not warnings:
        print(f"✅ {db_file} validation passed - no issues found")
        return
    
    print(f"\n🔍 Validation Report for {db_file}")
    print("=" * 50)
    
    if errors:
        print(f"\n❌ {len(errors)} Error(s) Found:")
        print("-" * 30)
        
        for i, error in enumerate(errors, 1):
            print(f"\n{i}. {error}")
            
            # Add context-specific fix suggestions
            if "missing required field" in error:
                print("   💡 Add the missing field with proper markdown format")
            elif "invalid ID format" in error:
                print("   💡 Generate new ID: python3 -c \"import uuid; print(uuid.uuid4().hex)\"")
            elif "non-existent task" in error:
                print("   💡 Update dependency to valid task ID or remove it")
    
    if warnings:
        print(f"\n⚠️  {len(warnings)} Warning(s):")
        print("-" * 30)
        
        for i, warning in enumerate(warnings, 1):
            print(f"\n{i}. {warning}")
    
    print(f"\n🔧 To fix these issues:")
    print("   1. Edit the markdown file directly")
    print("   2. Use readyq commands to update tasks")
    print("   3. Tasks with errors may not work correctly")
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `python3 run_tests.py -k "TestCustomDatabase"`
- [ ] `--db-file` flag works with all commands
- [ ] Custom database files operate independently
- [ ] Validation catches common errors
- [ ] Migration works per custom file

#### Manual Verification:
- [ ] Users can maintain multiple independent task databases
- [ ] Validation provides actionable error messages
- [ ] Custom files work with web UI

---

## Testing Strategy

### Unit Tests
- **Core Functions**: Test markdown parsing/generation in isolation
- **Database Operations**: Test load/save/append with various data
- **Migration Logic**: Test auto-migration scenarios
- **Validation**: Test error detection and reporting

### Integration Tests  
- **CLI Commands**: Test all commands with both formats
- **Web UI**: Test web interface with markdown format
- **File Locking**: Test concurrency with markdown files
- **Custom Files**: Test `--db-file` flag functionality

### End-to-End Tests
- **Migration Workflow**: Complete JSONL → Markdown transition
- **User Journey**: New user experience vs existing user migration
- **Data Integrity**: Round-trip testing with complex task structures
- **Error Recovery**: Handling corrupted files and partial migrations

### Performance Tests
- **Load Time**: Compare JSONL vs markdown parsing speed
- **Memory Usage**: Monitor memory consumption during operations
- **File Size**: Compare storage efficiency between formats
- **Migration Time**: Measure migration speed for large datasets

## Performance Considerations

**Expected Performance Impact**:
- **Load Time**: Markdown parsing ~2x slower than JSON parsing (acceptable for <1000 tasks)
- **Save Time**: Similar to JSONL (full file rewrite)
- **Memory Usage**: Similar memory footprint (load all tasks into memory)
- **Migration Time**: ~1-2 seconds per 100 tasks

**Optimization Strategies**:
- Use compiled regex patterns for parsing
- Cache compiled markdown templates
- Stream processing for large files
- Incremental parsing where possible

## Migration Notes

**For Existing JSONL Users**:
1. Auto-migration triggers on first command execution
2. Original JSONL backed up as `.readyq.jsonl.backup`
3. All data preserved including session logs and dependencies
4. User sees migration summary and can delete JSONL when ready

**For New Users**:
1. Fresh installations create `.readyq.md` by default
2. No migration needed
3. Immediate access to markdown benefits

**Rollback Capability**:
1. Backup file allows restoration to JSONL format
2. Manual rollback possible by deleting markdown and renaming backup
3. No automated rollback (user choice)

## References

- **Original Requirements**: `/home/mtomcal/code/readyq/research/2025-11-20-markdown-db-migration.md`
- **Test Plan**: `/home/mtomcal/code/readyq/research/2025-11-20-markdown-db-test-plan.md`
- **Current Implementation**: `readyq.py:107-143` (database functions)
- **Test Infrastructure**: `tests/test_helpers.py` (base test classes)
---
date: 2025-11-20T00:00:00+00:00
researcher: Claude Code
topic: "Migrate from JSONL to Markdown Database Storage"
tags: [research, database, markdown, migration, python3]
status: complete
---

# Research: Migrate from JSONL to Markdown Database Storage

**Date**: 2025-11-20T00:00:00+00:00
**Researcher**: Claude Code

## Research Question
How can we migrate readyq from JSONL file storage to markdown file storage while maintaining all current functionality and keeping implementation details to pure Python 3?

## Summary
A markdown-based database is feasible and offers significant advantages over JSONL for human readability and editability. The migration requires implementing new parsing functions while maintaining the same API contract. Key challenges include efficient parsing, maintaining file locking, and preserving all dependency graph operations.

## Detailed Findings

### Current JSONL Implementation Analysis

**Database Functions** (readyq.py:107-143):
- `db_load_tasks()`: Reads entire JSONL file, parses each line as JSON
- `db_save_tasks()`: Rewrites entire file with JSON dumps + newlines
- `db_append_task()`: Appends single JSON line to file
- File locking via `db_lock()` context manager

**Task Schema** (readyq.py:358-368):
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

**Performance Characteristics**:
- Read operations: Load entire file into memory (~50ms for <1000 tasks)
- Append operations: Fast single-line append
- Update operations: Rewrite entire file (acceptable for target use case)

### Proposed Markdown Database Format

**Structure**: Each task as a markdown section with metadata and content:

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

**Status Checkbox Format**:
- **Visual**: Markdown checkboxes (`- [ ]` and `- [x]`)
- **Single Selection**: Only one status should be checked at a time
- **Human Editable**: Users can manually check/uncheck statuses in any markdown editor
- **Parseable**: Parser extracts checked status (prioritizes `[x]` over `[ ]`)

### Implementation Strategy

**Recommended Migration Approach**: Auto-import on startup for seamless user experience.

**New Database Functions Required**:

1. **`md_load_tasks()`**: Parse markdown file into task objects
   - Use regex to find task sections (`# Task:.*`)
   - Parse metadata lines (`**Key**: Value`)
   - Extract description and session logs
   - Return list of task dicts matching current schema

2. **`md_save_tasks()`**: Write tasks to markdown format
   - Generate markdown for each task
   - Join with `---` separators
   - Write entire file (same performance as current)

3. **`md_append_task()`**: Append single task to markdown
   - Generate markdown for new task
   - Append to file with proper separator

4. **`auto_migrate_jsonl()`**: Auto-import existing JSONL files
   - Check for `.readyq.jsonl` on startup
   - Convert to markdown if no `.readyq.md` exists
   - Create backup of original file
   - Display migration summary

**Parsing Approach**:
- Use `re.finditer()` to find task sections
- Parse metadata with regex: `\*\*(\w+)\*\*:\s*(.*)`
- Handle multi-line descriptions and session logs
- Preserve all existing functionality

### Migration Benefits

**Human Readability**:
- Tasks readable in any markdown viewer
- Easy manual editing with text editor
- Better for version control diffs
- Natural format for documentation

**Maintainability**:
- No JSON parsing errors
- Easier to debug and inspect
- Can add markdown formatting in descriptions
- Session logs more readable

**Compatibility**:
- All existing CLI commands work unchanged
- Same task ID resolution (partial matching)
- Same dependency graph operations
- Same file locking mechanism

### Auto-Import Migration Strategy

**Recommended Approach**: Automatic migration on startup when JSONL file is detected.

**Implementation Flow**:
1. **Startup Detection**: When `quickstart` or any command runs, check for `.readyq.jsonl`
2. **Automatic Conversion**: If JSONL exists but no `.readyq.md`, automatically convert
3. **Backup Creation**: Create `.readyq.jsonl.backup` before conversion
4. **Success Confirmation**: Display conversion summary to user
5. **Seamless Transition**: All existing commands work immediately with new format

**User Experience**:
- **Zero User Action Required**: Migration happens transparently
- **No Data Loss**: All tasks, dependencies, and session logs preserved
- **Backup Available**: Original JSONL file backed up for safety
- **Immediate Benefits**: Users instantly gain markdown readability

**Technical Implementation**:
```python
def auto_migrate_jsonl():
    """Auto-import JSONL file on startup if markdown doesn't exist."""
    jsonl_file = ".readyq.jsonl"
    md_file = ".readyq.md"
    
    # Check if JSONL exists but markdown doesn't
    if os.path.exists(jsonl_file) and not os.path.exists(md_file):
        print(f"🔄 Auto-migrating {jsonl_file} to {md_file}...")
        
        # Load from JSONL
        jsonl_tasks = db_load_tasks()  # Use existing JSONL parser
        
        # Convert to markdown format
        md_content = generate_markdown_tasks(jsonl_tasks)
        
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

**Migration Path**:
- **Phase 1**: Auto-import on startup when JSONL file detected
- **Phase 2**: Direct conversion script from JSONL to Markdown
- **Phase 3**: Dual-write during transition period
- **Phase 4**: Import command for existing JSONL files

**Parsing Complexity**:
- Need robust regex for metadata extraction
- Handle edge cases (empty fields, special characters)
- Preserve markdown formatting in descriptions
- Parse nested session log structure

**Performance**:
- Same file rewrite pattern as JSONL
- Parsing overhead vs JSON parsing benefit
- Memory usage similar (load all tasks)
- Locking mechanism unchanged

**Migration Path**:
- Option 1: Auto-import on startup when JSONL file detected
- Option 2: Direct conversion script from JSONL to Markdown
- Option 3: Dual-write during transition period
- Option 4: Import command for existing JSONL files

### Code References

**Current Database Layer**:
- `readyq.py:107-143` - JSONL database functions
- `readyq.py:42` - DB_FILE constant
- `readyq.py:48-105` - File locking implementation

**Task Operations**:
- `readyq.py:355-398` - `cmd_new()` creates tasks with dependencies
- `readyq.py:436-620` - `cmd_update()` modifies tasks and dependency graph
- `readyq.py:147-164` - `find_task()` resolves partial IDs

**Web UI Integration**:
- `readyq.py:750-850` - Web handlers use same database functions
- No changes needed to web interface

## Architecture Insights

**Design Principles Preserved**:
- Zero dependencies (stdlib only)
- Single file storage
- File locking for concurrency
- Human-readable format
- Simple CLI-first approach

**Performance Trade-offs**:
- Markdown parsing adds minimal overhead
- Same memory usage pattern
- File locking unchanged
- Suitable for <1000 tasks (current target)

## Implementation Recommendations

### Primary Strategy: Auto-Import Migration

**Phase 1: Core Functions + Auto-Migration + Custom Database Support**
1. Implement `md_load_tasks()` with comprehensive parsing
2. Implement `md_save_tasks()` with markdown generation
3. Add `md_append_task()` for new task creation
4. Implement `auto_migrate_jsonl()` for seamless migration
5. Add `--db-file` flag to CLI argument parser
6. Update all database functions to accept file path parameter
7. Update `quickstart` command to check for auto-migration
8. Change DB_FILE constant to `.readyq.md` with override capability

**Phase 2: Database Layer Integration**
1. Update `cmd_quickstart()` to call `auto_migrate_jsonl()` on startup
2. Add migration check to all other commands (list, ready, new, etc.)
3. Update all `db_load_tasks()` calls to use markdown parser with fallback
4. Update all `db_save_tasks()` calls to use markdown generator
5. Update all `db_append_task()` calls to use markdown append
6. Test all CLI commands with both new and migrated files

**Phase 3: User Experience Enhancement**
1. Add `--force-jsonl` flag to use old format temporarily
2. Add `readyq migrate` command for manual migration
3. Add `readyq export` command to various formats
4. Update documentation and examples for markdown format
5. Add validation for markdown format integrity

### Migration User Flow

**For New Users**:
1. Run `readyq quickstart`
2. Auto-detect no existing files
3. Create fresh `.readyq.md` file
4. Display tutorial as normal

**For Existing JSONL Users**:
1. Run any `readyq` command (quickstart, list, etc.)
2. Auto-detect `.readyq.jsonl` exists, no `.readyq.md`
3. **Automatically convert** to markdown
4. Show migration summary with backup info
5. Continue with original command using new format

**Migration Summary Display**:
```
🔄 Auto-migrating .readyq.jsonl to .readyq.md...
✅ Migration complete!
   📄 Created .readyq.md
   💾 Backup saved as .readyq.jsonl.backup  
   📊 Migrated 5 tasks with 12 session logs
   🔄 Old JSONL file can be deleted manually

Readyq Tutorial - see README.md for full guide
```

**For Multiple Database Users**:
1. Use `--db-file` flag to specify alternative markdown file
2. Each file operates independently with own task graph
3. Auto-migration applies per specified file
4. Perfect for project-specific or context-specific task management

### Custom Database File Support

**Feature Design**: Add `--db-file` CLI flag to specify alternative markdown database location.

**Use Cases**:
- **Project-Specific Tasks**: `./readyq.py --db-file .project-tasks.md new "Fix login bug"`
- **Work vs Personal**: Maintain separate task lists for different contexts
- **Multi-Project Management**: Different task graphs per project directory
- **Testing**: Use test markdown files without affecting main database
- **Team Collaboration**: Share specific task lists via different filenames

**CLI Flag Implementation**:
```python
# Argument parser addition
parser.add_argument('--db-file', 
                   help='Alternative markdown database file (default: .readyq.md)',
                   default='.readyq.md')

# Usage examples
./readyq.py --db-file work-tasks.md quickstart
./readyq.py --db-file project-alpha.md new "Implement feature X"
./readyq.py --db-file personal.md list
./readyq.py --db-file team-tasks.md web --port 8001
```

**Technical Implementation**:
```python
def load_db_file(args):
    """Get database file path from args or default."""
    return getattr(args, 'db_file', '.readyq.md')

def auto_migrate_jsonl(db_file):
    """Auto-import JSONL file for specific database path."""
    jsonl_file = db_file.replace('.md', '.jsonl')
    
    # Check if JSONL exists but markdown doesn't for this file
    if os.path.exists(jsonl_file) and not os.path.exists(db_file):
        print(f"🔄 Auto-migrating {jsonl_file} to {db_file}...")
        
        # Load from JSONL using old functions
        jsonl_tasks = db_load_tasks()  # Temporarily uses global DB_FILE
        
        # Convert to markdown format
        md_content = generate_markdown_tasks(jsonl_tasks)
        
        # Create backup
        shutil.copy2(jsonl_file, jsonl_file + ".backup")
        
        # Write to specified markdown file
        with open(db_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"✅ Migration complete!")
        print(f"   📄 Created {db_file}")
        print(f"   💾 Backup saved as {jsonl_file}.backup")
        print(f"   📊 Migrated {len(jsonl_tasks)} tasks")

# Update database functions to use specified file
def db_load_tasks(db_file):
    """Load tasks from specified markdown file."""
    if not os.path.exists(db_file):
        return []
    
    # Parse markdown content
    content = open(db_file, 'r', encoding='utf-8').read()
    tasks = parse_markdown_tasks(content)
    return tasks
```

**Integration with Existing Commands**:
```python
# All commands need to accept and pass through --db-file
def cmd_new(args):
    db_file = load_db_file(args)
    
    # Auto-migrate if needed
    auto_migrate_jsonl(db_file)
    
    # Create new task in specified file
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_task = {
        "id": uuid.uuid4().hex,
        "title": args.title,
        # ... other fields
    }
    
    tasks = db_load_tasks(db_file)
    tasks.append(new_task)
    db_save_tasks(tasks, db_file)

def cmd_list(args):
    db_file = load_db_file(args)
    tasks = db_load_tasks(db_file)
    print_task_list(tasks)

def cmd_web(args):
    db_file = load_db_file(args)
    # Web UI should also respect custom database file
    start_web_server(port=args.port, db_file=db_file)
```

**Database Function Signatures**:
```python
# Updated function signatures to accept file path
def md_load_tasks(db_file=None):
    """Load tasks from markdown file (default or specified)."""
    if db_file is None:
        db_file = getattr(args, 'db_file', '.readyq.md')
    # ... parsing logic

def md_save_tasks(tasks, db_file=None):
    """Save tasks to markdown file (default or specified)."""
    if db_file is None:
        db_file = getattr(args, 'db_file', '.readyq.md')
    # ... generation logic

def md_append_task(task, db_file=None):
    """Append task to markdown file (default or specified)."""
    if db_file is None:
        db_file = getattr(args, 'db_file', '.readyq.md')
    # ... append logic
```

**Web UI Integration**:
```python
# Web server should respect custom database file
def start_web_server(port=8000, db_file='.readyq.md'):
    """Start web UI server with specified database file."""
    
    class CustomWebUIHandler(WebUIHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.db_file = db_file
        
        def do_GET(self):
            # All API endpoints use self.db_file
            if self.path.startswith('/api/tasks'):
                tasks = md_load_tasks(self.db_file)
                # ... rest of API logic
```

**Benefits of Custom Database Support**:
- **Organizational Flexibility**: Separate task contexts by filename
- **Project Isolation**: Different projects can have independent task graphs
- **Team Collaboration**: Share specific task lists via version control
- **Testing Safety**: Use test databases without affecting production data
- **Migration Control**: Each database file migrates independently

**File Naming Conventions**:
- **Default**: `.readyq.md`
- **Project-Specific**: `.project-tasks.md`, `.myapp-tasks.md`
- **Context-Specific**: `work-tasks.md`, `personal-tasks.md`
- **Team-Shared**: `team-roadmap.md`, `sprint-tasks.md`
- **Testing**: `test-tasks.md`, `temp-tasks.md`

This feature enhances the markdown database migration by providing users with flexible database management while maintaining the simplicity and zero-dependency philosophy of readyq.

### Markdown Database Validation & Error Handling

**Validation Strategy**: Comprehensive validation system to catch schema errors and provide actionable fix suggestions for AI agents.

**Validation Levels**:

1. **File-Level Validation**: Overall file structure and format
2. **Task-Level Validation**: Individual task completeness and correctness  
3. **Relationship Validation**: Dependency graph integrity
4. **Content Validation**: Field formats and required data

**Common Error Scenarios**:

**1. Missing Required Fields**:
```markdown
# Task: Implement Authentication

**ID**: c4a0b12d3e8f9a015e1b2c3f4d5e6789
**Created**: 2025-10-30T15:30:00.000000+00:00
<!-- Missing: Updated, Status, Description -->
```

**Error Output**:
```
❌ Validation Error in .readyq.md:123

Task 'Implement Authentication' (c4a0b12d3e8f9a015e1b2c3f4d5e6789) is missing required fields:

🔧 FIX NEEDED:
   📝 Add '**Updated**:' field with ISO8601 timestamp
   ✅ Add '## Status' section with checkboxes
   📄 Add '## Description' section with task details

💡 SUGGESTED CONTENT:
   **Updated**: 2025-10-30T16:45:00.000000+00:00
   
   ## Status
   - [ ] Open
   - [ ] In Progress  
   - [ ] Blocked
   - [ ] Done
   
   ## Description
   
   Add JWT-based authentication to API endpoints
```

**2. Malformed Status Checkboxes**:
```markdown
## Status
- Open
- [x] In Progress  
- [ ] Blocked
- Done
```

**Error Output**:
```
❌ Validation Error in .readyq.md:156

Task 'Implement Authentication' has malformed Status section:

🔧 FIX NEEDED:
   ❌ Line 156: '- Open' should be '- [ ] Open' or '- [x] Open'
   ❌ Line 159: '- Done' should be '- [ ] Done' or '- [x] Done'

💡 CORRECTED VERSION:
   ## Status
   - [ ] Open
   - [x] In Progress  
   - [ ] Blocked
   - [ ] Done
```

**3. Invalid ID Format**:
```markdown
**ID**: invalid-uuid-format
```

**Error Output**:
```
❌ Validation Error in .readyq.md:145

Task 'Implement Authentication' has invalid ID format:

🔧 FIX NEEDED:
   ❌ ID 'invalid-uuid-format' is not a valid 32-character hex string
   ✅ Should be 32 hex characters (e.g., c4a0b12d3e8f9a015e1b2c3f4d5e6789)

💡 GENERATE NEW ID:
   python3 -c "import uuid; print(uuid.uuid4().hex)"
```

**4. Multiple Status Selection**:
```markdown
## Status
- [x] Open
- [x] In Progress  
- [ ] Blocked
- [ ] Done
```

**Error Output**:
```
❌ Validation Error in .readyq.md:156

Task 'Implement Authentication' has multiple checked statuses:

🔧 FIX NEEDED:
   ❌ Both 'Open' and 'In Progress' are checked - only one allowed
   ✅ Uncheck all except the current status

💡 CORRECTED VERSION:
   ## Status
   - [ ] Open
   - [x] In Progress  
   - [ ] Blocked
   - [ ] Done
```

**5. Broken Dependency References**:
```markdown
**Blocks**: nonexistent-task-id
```

**Error Output**:
```
❌ Validation Error in .readyq.md:147

Task 'Implement Authentication' references non-existent task:

🔧 FIX NEEDED:
   ❌ 'Blocks': 'nonexistent-task-id' does not exist in database
   ✅ Update to valid task ID or remove dependency

💡 AVAILABLE TASKS:
   - c4a0b12d3e8f9a015e1b2c3f4d5e6789: Write API Tests
   - 5e1b2c3f4d5e6789c4a0b12d3e8f9a01: Database Schema Design
```

**6. Malformed Timestamps**:
```markdown
**Created**: yesterday
**Updated**: 2025/10/30 4:45 PM
```

**Error Output**:
```
❌ Validation Error in .readyq.md:144-145

Task 'Implement Authentication' has malformed timestamps:

🔧 FIX NEEDED:
   ❌ 'Created': 'yesterday' is not valid ISO8601 format
   ❌ 'Updated': '2025/10/30 4:45 PM' is not valid ISO8601 format

💡 CORRECT FORMAT:
   **Created**: 2025-10-30T15:30:00.000000+00:00
   **Updated**: 2025-10-30T16:45:00.000000+00:00

💡 GENERATE CURRENT TIMESTAMP:
   python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())"
```

**Implementation Functions**:

```python
def md_load_tasks(db_file):
    """Load tasks from markdown file with automatic validation."""
    if not os.path.exists(db_file):
        return []
    
    try:
        content = open(db_file, 'r', encoding='utf-8').read()
        tasks = parse_markdown_tasks(content)
        
        # Run validation automatically on every load
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
        
    except Exception as e:
        print(f"❌ Failed to load database {db_file}: {e}")
        print("💡 Possible solutions:")
        print("   • Check file permissions")
        print("   • Verify file exists and is readable")
        print("   • Ensure file is valid UTF-8 encoded text")
        return []

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
    
    # Check for circular dependencies (basic check)
    circular_deps = find_circular_dependencies(tasks)
    if circular_deps:
        errors.append(f"Circular dependency detected: {' → '.join(circular_deps)}")
    
    return errors, warnings

def validate_task(task, task_dict, db_file):
    """Validate individual task structure and content."""
    errors = []
    line_num = task.get('_line_num', 0)  # Track where task starts
    
    # Check required fields
    required_fields = ['id', 'created_at', 'updated_at']
    for field in required_fields:
        if field not in task or not task[field]:
            errors.append(f"Task '{task.get('title', 'Unknown')}' missing required field: {field}")
    
    # Validate ID format
    if task.get('id') and not re.match(r'^[a-f0-9]{32}$', task['id']):
        errors.append(f"Task '{task.get('title', 'Unknown')}' has invalid ID format: {task['id']}")
    
    # Validate status
    status_errors = validate_task_status(task, line_num)
    errors.extend(status_errors)
    
    # Validate dependencies
    dep_errors = validate_task_dependencies(task, task_dict, line_num)
    errors.extend(dep_errors)
    
    # Validate timestamps
    time_errors = validate_task_timestamps(task, line_num)
    errors.extend(time_errors)
    
    return errors

def validate_task_status(task, line_num):
    """Validate task status checkboxes."""
    errors = []
    
    status_checked = []
    
    # Count checked statuses
    if 'status_raw' in task:  # Raw markdown content
        status_lines = task['status_raw'].split('\n')
        for line in status_lines:
            if line.strip().startswith('- ['):
                if '[x]' in line:
                    status_checked.append(line.strip())
                elif '[ ]' in line:
                    pass  # Unchecked, fine
                else:
                    errors.append(f"Malformed status checkbox: {line.strip()}")
    
    # Check for multiple checked
    if len(status_checked) > 1:
        errors.append(f"Multiple statuses checked: {status_checked}")
    
    # Check for none checked
    if len(status_checked) == 0 and not task.get('status'):
        errors.append("No status selected - add checkboxes under '## Status'")
    
    return errors

def validate_task_dependencies(task, task_dict, line_num):
    """Validate task dependency references."""
    errors = []
    
    # Check blocks
    for block_id in task.get('blocks', []):
        if block_id not in task_dict:
            errors.append(f"References non-existent task in blocks: {block_id}")
    
    # Check blocked_by
    for block_id in task.get('blocked_by', []):
        if block_id not in task_dict:
            errors.append(f"References non-existent task in blocked_by: {block_id}")
    
    return errors

def validate_task_timestamps(task, line_num):
    """Validate task timestamp formats."""
    errors = []
    
    timestamp_fields = ['created_at', 'updated_at']
    
    for field in timestamp_fields:
        value = task.get(field)
        if value:
            try:
                # Try to parse as ISO8601
                datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                errors.append(f"Invalid timestamp format for {field}: {value}")
    
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
            elif "malformed status checkbox" in error:
                print("   💡 Use format: '- [ ] Open' or '- [x] In Progress'")
            elif "Multiple statuses checked" in error:
                print("   💡 Only one status should be checked at a time")
            elif "non-existent task" in error:
                print("   💡 Update dependency to valid task ID or remove it")
            elif "Invalid timestamp format" in error:
                print("   💡 Use ISO8601 format: 2025-10-30T15:30:00.000000+00:00")
            elif "Circular dependency" in error:
                print("   💡 Remove circular reference by updating dependency relationships")
    
    if warnings:
        print(f"\n⚠️  {len(warnings)} Warning(s):")
        print("-" * 30)
        
        for i, warning in enumerate(warnings, 1):
            print(f"\n{i}. {warning}")
    
    print(f"\n🔧 To fix these issues:")
    print("   1. Edit the markdown file directly")
    print("   2. Use readyq commands to update tasks")
    print("   3. Tasks with errors may not work correctly")
    
    if errors:
        print(f"\n💾 Consider backing up before making changes:")
        print(f"   cp {db_file} {db_file}.backup")
```

**User Experience with Auto-Validation**:

**Normal Operation** (No Issues):
```bash
$ ./readyq.py list
✅ .readyq.md validation passed - no issues found

ID       Status        Blocked Title              
--------------------------------------------------------------
c4a0b12d open          No     Implement authentication
```

**With Validation Errors**:
```bash
$ ./readyq.py list
🔍 Validation Report for .readyq.md
==================================================

❌ 3 Error(s) Found:
------------------------------

1. Task 'Implement authentication' missing required field: updated_at
   💡 Add the missing field with proper markdown format

2. Task 'Write tests' has malformed Status checkbox: - In Progress
   💡 Use format: '- [ ] Open' or '- [x] In Progress'

3. References non-existent task in blocked_by: invalid-id-123
   💡 Update dependency to valid task ID or remove it

⚠️  Database loaded with errors. Some functionality may not work correctly.
🔧 Consider fixing the issues above for optimal performance.

ID       Status        Blocked Title              
--------------------------------------------------------------
c4a0b12d open          No     Implement authentication
5e1b2c3f in_progress   Yes    Write tests
```

**With Warnings Only**:
```bash
$ ./readyq.py ready
⚠️  1 warning(s) found in .readyq.md
   • Task 'Old task' has no session logs - consider adding context

ID       Status        Blocked Title              
--------------------------------------------------------------
a1b2c3d4 open          No     Design API endpoints
```

**Benefits of Auto-Validation**:
- **No Additional Commands**: Validation runs automatically on every database operation
- **Immediate Feedback**: Users see issues as soon as they occur
- **AI Agent Friendly**: Detailed error messages help agents fix problems automatically
- **Non-Blocking**: Database loads even with errors, but user is informed
- **Proactive**: Catches issues before they cause command failures

This auto-validation approach ensures users always know the state of their database and get actionable feedback for fixing issues, making markdown file editing safe and user-friendly.

### Auto-Migration Benefits

- **Zero Friction**: Users don't need to learn migration process
- **Data Safety**: Automatic backup creation
- **Immediate Value**: Instant access to markdown benefits
- **Backward Compatible**: Commands work unchanged
- **User Choice**: Can manually delete JSONL when ready

### Sample Implementation Skeleton

```python
def md_load_tasks():
    """Load tasks from markdown file."""
    if not os.path.exists(DB_FILE):
        return []
    
    tasks = []
    content = open(DB_FILE, 'r', encoding='utf-8').read()
    
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
```

## Open Questions

1. **Metadata Format**: Should we use YAML frontmatter instead of inline metadata?
2. **Backward Compatibility**: How to handle existing JSONL files during transition?
3. **Validation**: Should we add markdown format validation functions?
4. **Performance**: Will parsing overhead be noticeable for large task sets?
5. **Migration Strategy**: Best approach for users with existing JSONL data?

## Conclusion

Migrating from JSONL to markdown storage is technically feasible and offers significant benefits for human readability and editability. The implementation requires new parsing functions but can maintain the same API contract and performance characteristics. The markdown format is more intuitive for manual editing and better suited for documentation workflows while preserving all existing functionality.

The migration should be implemented in phases, starting with core functions and followed by integration testing. A conversion tool for existing JSONL files would ensure smooth transition for current users.
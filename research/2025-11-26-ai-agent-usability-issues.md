---
date: 2025-11-26T21:05:00+00:00
researcher: Claude (Sonnet 4.5)
topic: "AI Agent Usability Issues with Quickstart and Multiline Descriptions"
tags: [research, usability, ai-agents, quickstart, cli]
status: complete
---

# Research: AI Agent Usability Issues with Quickstart and Multiline Descriptions

**Date**: 2025-11-26
**Researcher**: Claude (Sonnet 4.5)

## Research Question
AI Agents are struggling with 1) inaccurate quickstart help 2) passing in multiline description into the --description flag. Figure out changes required to make this easier.

## Summary

Found **two critical issues** affecting AI agent usability:

1. **Quickstart Inaccuracy**: The quickstart tutorial displays outdated database information (says `.readyq.jsonl` when it's actually `.readyq.md`)
2. **Multiline Description Documentation**: While multiline descriptions DO work correctly, there's NO documentation showing AI agents how to pass them via CLI

## Detailed Findings

### Issue 1: Inaccurate Database Location in Quickstart

**Location**: `readyq.py:773-777`

The quickstart command displays:
```
DATABASE LOCATION
─────────────────

Default: ./.readyq.jsonl (in current directory)
Format:  JSONL (one JSON task per line, git-friendly)
```

**Problem**: This is outdated! The actual database file is `.readyq.md` (markdown format) as of the recent migration from JSONL to markdown.

**Evidence**:
- `readyq.py:52` - `DB_FILE = ".readyq.md"`
- `readyq.py:4` - Docstring says "markdown-based task tracker"
- `readyq.py:26` - Features list says "Human-readable markdown database format (.readyq.md)"

**Impact**: AI agents reading the quickstart tutorial will:
- Look for the wrong file (`.readyq.jsonl` vs `.readyq.md`)
- Think the format is JSONL when it's actually markdown
- Be confused about the actual database structure

### Issue 2: Missing Multiline Description Documentation

**Current Status**: Multiline descriptions WORK correctly via CLI!

**Test Results**:
```bash
# This works perfectly:
./readyq.py new "Test task" --description "Line 1
Line 2
Line 3"

# Output shows preserved newlines:
Description:
Line 1
Line 2
Line 3
```

**The Problem**: There's NO documentation showing AI agents HOW to pass multiline strings:

1. **Quickstart Tutorial** (`readyq.py:678-683`):
   ```bash
   ./readyq.py new "Set up database schema"
   ./readyq.py new "Build API endpoints" --description "REST API for user management"
   ```
   Only shows single-line descriptions!

2. **README.md** (`README.md:27-28`):
   ```bash
   ./readyq.py new "Implement authentication" --description "Add JWT-based auth to API endpoints"
   ```
   Only shows single-line examples!

3. **No Examples in `/examples/` directory**: None of the example scripts use `--description` at all

**What AI Agents Need**: Clear examples of bash techniques for multiline strings:

Common bash patterns for multiline strings:
- `$'...'` syntax: `--description $'Line 1\nLine 2\nLine 3'`
- Literal quotes: `--description "Line 1
  Line 2
  Line 3"`
- Variables: `DESC=$'Multi\nLine'; ./readyq.py new "Task" --description "$DESC"`
- Heredocs: `DESC=$(cat <<'EOF'
  Line 1
  Line 2
  EOF
  ); ./readyq.py new "Task" --description "$DESC"`

## Code References

### Quickstart Command
- `readyq.py:648-793` - Full quickstart command implementation
- `readyq.py:773-777` - **OUTDATED** database location section
- `readyq.py:678-683` - Example task creation (only single-line descriptions)

### Description Handling
- `readyq.py:795-837` - `cmd_new()` function (handles description correctly)
- `readyq.py:2971` - Argparse definition: `parser_new.add_argument("--description", type=str, help="Detailed description of the task.")`
- `readyq.py:3005` - Argparse definition: `parser_update.add_argument("--description", type=str, help="Update the task description.")`

### Markdown Database Format
- `readyq.py:52` - `DB_FILE = ".readyq.md"`
- `readyq.py:157-180` - `md_load_tasks()` - Loads markdown format
- `readyq.py:254-292` - `generate_markdown_task()` - Generates markdown output
- `readyq.py:237-240` - Multiline description parsing with `re.DOTALL`

### Documentation Files
- `README.md:1-200` - Main README (shows only single-line descriptions)
- `examples/03-ai-agent-workflow.sh` - AI agent example (no descriptions used)
- `CLAUDE.md:679-683` - Project instructions for Claude (only single-line examples)

## Architecture Insights

### Multiline Strings Work Because:
1. **Python's argparse handles them natively**: `type=str` accepts any string including newlines
2. **Shell preserves newlines in quotes**: Bash/sh treat quoted strings with newlines as single arguments
3. **Markdown format preserves formatting**: The markdown parser uses `re.DOTALL` flag to match across newlines

### Why AI Agents Struggle:
1. **No examples in documentation**: AI agents learn from examples, and all examples show single-line only
2. **Ambiguous documentation**: No explicit mention that multiline is supported
3. **Shell knowledge gap**: AI agents may not know bash string quoting rules without examples

## Required Changes

### 1. Fix Quickstart Database Location (HIGH PRIORITY)

**File**: `readyq.py:773-777`

**Current**:
```
DATABASE LOCATION
─────────────────

Default: ./.readyq.jsonl (in current directory)
Format:  JSONL (one JSON task per line, git-friendly)
```

**Should be**:
```
DATABASE LOCATION
─────────────────

Default: ./.readyq.md (in current directory)
Format:  Markdown (human-readable, git-friendly)

Note: Old JSONL files (.readyq.jsonl) are auto-migrated on first run.
```

### 2. Add Multiline Description Examples to Quickstart (HIGH PRIORITY)

**File**: `readyq.py:678-683`

**Add after current examples**:
```
   # Tasks with detailed multi-line descriptions
   ./readyq.py new "Refactor authentication" --description $'This task involves:\n- Updating JWT implementation\n- Adding refresh token support\n- Improving error handling'

   # Or using literal newlines in quotes
   ./readyq.py new "Database migration" --description "Step 1: Backup current data
   Step 2: Run migration scripts
   Step 3: Verify integrity"
```

### 3. Add Multiline Examples to README (MEDIUM PRIORITY)

**File**: `README.md` around line 84-92

**Add section**:
```markdown
### Multiline Descriptions

You can pass multiline descriptions using standard bash string quoting:

```bash
# Using $'...\n...' syntax
./readyq.py new "Refactor auth system" --description $'Requirements:\n- Add JWT refresh tokens\n- Improve error handling\n- Add rate limiting'

# Using literal newlines (press Enter inside quotes)
./readyq.py new "Database migration" --description "Step 1: Backup data
Step 2: Run migrations
Step 3: Verify integrity"

# Using heredocs for very long descriptions
DESC=$(cat <<'EOF'
This is a complex task requiring:
1. Research phase
2. Implementation phase
3. Testing phase
EOF
)
./readyq.py new "Complex task" --description "$DESC"
```
```

### 4. Add Example Script with Descriptions (LOW PRIORITY)

**File**: Create `examples/04-detailed-descriptions.sh`

```bash
#!/bin/bash
# Example 4: Using Detailed Task Descriptions
# Shows how to create tasks with multiline descriptions

echo "=== Task Descriptions Example ==="

# Single-line description
./readyq.py new "Quick task" --description "Simple one-line description"

# Multi-line using $'...\n...' syntax
./readyq.py new "Complex refactoring" --description $'This task requires:\n- Code analysis\n- Design planning\n- Implementation\n- Testing'

# Multi-line using literal newlines
./readyq.py new "Database migration" --description "Phase 1: Backup all data
Phase 2: Run migration scripts
Phase 3: Verify data integrity
Phase 4: Update documentation"

# Using heredoc for very detailed descriptions
DETAILED_DESC=$(cat <<'EOF'
CONTEXT:
The authentication system needs a complete overhaul to support modern OAuth2 flows.

REQUIREMENTS:
1. Implement OAuth2 authorization code flow
2. Add refresh token rotation
3. Support multiple identity providers (Google, GitHub, Microsoft)
4. Implement proper token revocation

ACCEPTANCE CRITERIA:
- All tests pass
- Documentation updated
- Security audit completed
EOF
)
./readyq.py new "Modernize authentication system" --description "$DETAILED_DESC"

echo ""
echo "=== Created tasks with various description styles ==="
./readyq.py list
```

### 5. Update CLAUDE.md Documentation (MEDIUM PRIORITY)

**File**: `CLAUDE.md:679-683`

Add note about multiline descriptions:
```markdown
1. CREATING TASKS
   Add new work items with titles and optional descriptions:

   ./readyq.py new "Set up database schema"
   ./readyq.py new "Build API endpoints" --description "REST API for user management"

   # Multi-line descriptions using $'...\n...' syntax
   ./readyq.py new "Complex task" --description $'Part 1: Research\nPart 2: Implement\nPart 3: Test'

   # Or using literal newlines in quotes
   ./readyq.py new "Migration task" --description "Step 1: Backup
   Step 2: Migrate
   Step 3: Verify"
```

## Testing Plan

### Manual Tests Required:

1. **Test quickstart output**:
   ```bash
   ./readyq.py quickstart | grep "DATABASE LOCATION" -A 5
   # Verify it shows .readyq.md, not .readyq.jsonl
   ```

2. **Test multiline descriptions**:
   ```bash
   # Test $'...\n...' syntax
   ./readyq.py new "Test 1" --description $'Line 1\nLine 2\nLine 3'

   # Test literal newlines
   ./readyq.py new "Test 2" --description "Line 1
   Line 2
   Line 3"

   # Verify output preserves newlines
   ./readyq.py show <task-id>
   ```

3. **Test example script** (if created):
   ```bash
   chmod +x examples/04-detailed-descriptions.sh
   ./examples/04-detailed-descriptions.sh
   ```

### Automated Tests:
Add to test suite:
```python
def test_multiline_description():
    """Test that multiline descriptions are preserved"""
    task_id = create_task("Test", description="Line 1\nLine 2\nLine 3")
    task = get_task(task_id)
    assert task['description'] == "Line 1\nLine 2\nLine 3"
    assert "\n" in task['description']
```

## Implementation Priority

**Priority Order**:
1. ✅ **CRITICAL**: Fix quickstart database location (readyq.py:773-777)
2. ✅ **HIGH**: Add multiline examples to quickstart (readyq.py:678-683)
3. ⬜ **MEDIUM**: Add multiline section to README.md
4. ⬜ **MEDIUM**: Update CLAUDE.md with multiline examples
5. ⬜ **LOW**: Create examples/04-detailed-descriptions.sh

**Estimated Time**: 30-45 minutes for all changes

## Open Questions

1. **Should we add a `--description-file` flag?**
   - Pro: Easier for very long descriptions
   - Con: Adds complexity, heredocs already work
   - Decision: Not needed for MVP, could add later if requested

2. **Should we validate description length?**
   - Current: No limit
   - Consideration: Markdown format can handle any length
   - Decision: No limit needed

3. **Should we add formatting help to the CLI help text?**
   - Current: `help="Detailed description of the task."`
   - Could be: `help="Detailed description (supports multiline via shell quoting)"`
   - Decision: Yes, update help text for both `new` and `update` commands

## Conclusion

The issues are straightforward to fix:
1. Update quickstart tutorial with correct database filename and format
2. Add clear examples of multiline description syntax
3. Document bash string quoting techniques for AI agents

**Impact**: These changes will significantly improve AI agent success rate with readyq by:
- Eliminating confusion about database location/format
- Providing clear patterns for multiline content
- Demonstrating proper shell quoting techniques

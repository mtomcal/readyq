# readyq Examples

This directory contains practical examples demonstrating various use cases for readyq.

## Running Examples

All examples are bash scripts. Make them executable and run:

```bash
chmod +x examples/*.sh
./examples/01-basic-usage.sh
```

**Note**: Each example creates a `.readyq.jsonl` file. You may want to run examples in separate directories or clean up between runs:

```bash
rm .readyq.jsonl
```

## Available Examples

### 1. Basic Usage (`01-basic-usage.sh`)

Demonstrates the fundamental workflow:
- Initializing readyq
- Creating tasks
- Listing tasks
- Viewing ready tasks
- Updating task status

**Best for**: First-time users learning the basics

### 2. Task Dependencies (`02-dependencies.sh`)

Shows how to create and manage task dependencies:
- Creating blocking relationships
- Automatic unblocking when dependencies complete
- Viewing only ready (unblocked) tasks

**Best for**: Understanding the dependency graph feature

### 3. AI Agent Workflow (`03-ai-agent-workflow.sh`)

Demonstrates how an AI agent might use readyq:
- Creating a multi-step task plan
- Querying for ready work
- Tracking progress through complex workflows
- Automatic dependency resolution

**Best for**: AI/automation use cases

## Manual Testing Scenarios

### Testing the Web UI

```bash
# Initialize and create some tasks
./readyq.py quickstart
./readyq.py new "Task 1"
./readyq.py new "Task 2"
./readyq.py new "Task 3" --blocked-by <task1-id>

# Launch web interface
./readyq.py --web
```

Then test in the browser:
1. View ready tasks vs. all tasks
2. Click "Start" to mark a task as in_progress
3. Click "Done" to complete a task
4. Watch dependent tasks automatically unblock
5. Click "Re-open" to revert a completed task

### Testing Edge Cases

```bash
# Ambiguous ID prefix
./readyq.py quickstart
./readyq.py new "Task A"
./readyq.py new "Task B"
./readyq.py update a --status done  # Should work if only one task starts with 'a'

# Invalid blocker
./readyq.py new "Task C" --blocked-by invalid-id  # Should warn but create task

# Non-existent task update
./readyq.py update nonexistent --status done  # Should show error

# Empty database
./readyq.py list  # Should handle gracefully
./readyq.py ready  # Should show "No tasks found"
```

### Testing Task Graphs

Create a complex dependency graph:

```bash
./readyq.py quickstart

# Create a diamond dependency:
#      A
#     / \
#    B   C
#     \ /
#      D

./readyq.py new "Task A"
A_ID=$(./readyq.py list | tail -1 | awk '{print $1}')

./readyq.py new "Task B" --blocked-by $A_ID
B_ID=$(./readyq.py list | tail -1 | awk '{print $1}')

./readyq.py new "Task C" --blocked-by $A_ID
C_ID=$(./readyq.py list | tail -1 | awk '{print $1}')

./readyq.py new "Task D" --blocked-by $B_ID,$C_ID

# Now test:
./readyq.py ready  # Should show only A
./readyq.py update $A_ID --status done
./readyq.py ready  # Should show B and C
./readyq.py update $B_ID --status done
./readyq.py ready  # Should show C (D still blocked)
./readyq.py update $C_ID --status done
./readyq.py ready  # Should show D (fully unblocked)
```

## Integration Examples

### Git Workflow

```bash
# Initialize in a project
cd ~/projects/myproject
readyq quickstart

# Add tasks
readyq new "Fix bug #123"
readyq new "Update dependencies"

# Track with git
git add .readyq.jsonl
git commit -m "Add task tracking"

# Update and commit
readyq update <id> --status done
git add .readyq.jsonl
git commit -m "Complete bug fix task"
```

### Cron Job for Daily Review

```bash
# Add to crontab: crontab -e
0 9 * * * cd ~/projects/myproject && /path/to/readyq.py ready | mail -s "Today's Ready Tasks" you@example.com
```

### Shell Alias for Quick Access

```bash
# Add to ~/.bashrc or ~/.zshrc
alias rqn='readyq.py new'
alias rql='readyq.py list'
alias rqr='readyq.py ready'
alias rqu='readyq.py update'

# Usage:
rqn "My new task"
rqr
rqu abc123 --status done
```

## Creating Your Own Examples

When creating new examples:

1. Start with `./readyq.py quickstart`
2. Show the command and its output
3. Explain what's happening
4. Clean up (or note that `.readyq.jsonl` will persist)
5. Add to this README

## Troubleshooting

**Issue**: "Command not found: ./readyq.py"
**Solution**: Make sure you're in the project root and readyq.py is executable:
```bash
chmod +x readyq.py
```

**Issue**: "File exists: .readyq.jsonl"
**Solution**: Remove the existing file or use a different directory:
```bash
rm .readyq.jsonl
# or
mkdir temp && cd temp
```

**Issue**: Web UI doesn't open
**Solution**: Check if port 8000 is available:
```bash
lsof -i :8000
# Kill conflicting process or edit PORT in readyq.py
```

---

Have a useful example? Contribute it! See `CONTRIBUTING.md`.

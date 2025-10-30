#!/bin/bash
# Example 1: Basic Usage
# This demonstrates the core workflow of readyq

echo "=== Basic readyq Usage Example ==="
echo ""

# Initialize
echo "1. Initialize task file"
./readyq.py quickstart
echo ""

# Create simple tasks
echo "2. Create tasks"
./readyq.py new "Review pull requests"
./readyq.py new "Write documentation"
./readyq.py new "Update dependencies"
echo ""

# View all tasks
echo "3. List all tasks"
./readyq.py list
echo ""

# View ready tasks
echo "4. Show ready tasks"
./readyq.py ready
echo ""

# Start working on a task
echo "5. Update task status (use the ID from above)"
echo "   Example: ./readyq.py update <task-id> --status in_progress"
echo ""

# Complete a task
echo "6. Mark task as done"
echo "   Example: ./readyq.py update <task-id> --status done"
echo ""

echo "=== Example Complete ==="
echo "Try these commands yourself with the task IDs shown above!"

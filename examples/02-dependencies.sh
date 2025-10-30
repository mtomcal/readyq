#!/bin/bash
# Example 2: Task Dependencies
# This demonstrates how to create and manage blocked tasks

echo "=== Task Dependencies Example ==="
echo ""

# Initialize
echo "1. Initialize"
./readyq.py quickstart
echo ""

# Create a task that blocks others
echo "2. Create a base task"
./readyq.py new "Design API schema"
echo "   Copy the task ID shown above"
echo ""
read -p "   Paste the task ID here: " DESIGN_ID
echo ""

# Create dependent tasks
echo "3. Create tasks that depend on the design"
./readyq.py new "Implement backend API" --blocked-by "$DESIGN_ID"
./readyq.py new "Write API tests" --blocked-by "$DESIGN_ID"
./readyq.py new "Create API documentation" --blocked-by "$DESIGN_ID"
echo ""

# Show ready tasks (only the design task)
echo "4. Show ready tasks (only unblocked tasks appear)"
./readyq.py ready
echo ""

# Complete the blocking task
echo "5. Complete the design task"
./readyq.py update "$DESIGN_ID" --status done
echo ""

# Show ready tasks again (now all tasks are unblocked)
echo "6. Show ready tasks again (dependent tasks are now unblocked)"
./readyq.py ready
echo ""

echo "=== Example Complete ==="
echo "Notice how completing the design task automatically unblocked the others!"

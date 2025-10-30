#!/bin/bash
# Example 3: AI Agent Workflow
# This demonstrates how an AI agent might use readyq

echo "=== AI Agent Workflow Example ==="
echo ""

# Initialize
echo "AI Agent: Initializing task queue..."
./readyq.py quickstart
echo ""

# Agent creates a task plan
echo "AI Agent: Creating task plan for codebase refactoring..."
./readyq.py new "Analyze current codebase structure"
ANALYZE_ID=$(./readyq.py list | tail -1 | awk '{print $1}')
echo ""

./readyq.py new "Identify refactoring opportunities" --blocked-by "$ANALYZE_ID"
IDENTIFY_ID=$(./readyq.py list | tail -1 | awk '{print $1}')
echo ""

./readyq.py new "Create refactoring plan" --blocked-by "$IDENTIFY_ID"
PLAN_ID=$(./readyq.py list | tail -1 | awk '{print $1}')
echo ""

./readyq.py new "Execute refactoring" --blocked-by "$PLAN_ID"
EXECUTE_ID=$(./readyq.py list | tail -1 | awk '{print $1}')
echo ""

./readyq.py new "Run tests and verify" --blocked-by "$EXECUTE_ID"
echo ""

# Agent checks what work is ready
echo "AI Agent: Checking for ready tasks..."
./readyq.py ready
echo ""

# Agent starts work
echo "AI Agent: Starting analysis task..."
./readyq.py update "$ANALYZE_ID" --status in_progress
echo ""

# Simulate work completion
echo "AI Agent: Analysis complete! (simulated)"
./readyq.py update "$ANALYZE_ID" --status done
echo ""

# Agent checks for next task
echo "AI Agent: Checking for next ready task..."
./readyq.py ready
echo ""

echo "AI Agent: Starting identification task..."
./readyq.py update "$IDENTIFY_ID" --status in_progress
echo ""

# Show current state
echo "Current state of all tasks:"
./readyq.py list
echo ""

echo "=== Example Complete ==="
echo "This shows how an AI agent can:"
echo "  - Create a dependency graph of work"
echo "  - Query for ready tasks"
echo "  - Track progress through complex workflows"

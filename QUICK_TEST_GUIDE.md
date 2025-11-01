# Quick Test Guide for readyq

## Run All Tests

```bash
python3 run_tests.py
```

Expected output: `✓ All tests passed!` with 56/56 tests passing.

## Run Tests by Category

```bash
python3 run_tests.py database     # Database operations (17 tests)
python3 run_tests.py helpers      # Helper functions (13 tests)
python3 run_tests.py cli          # CLI commands (14 tests)
python3 run_tests.py concurrency  # File locking (12 tests)
```

## Run with Coverage

```bash
python3 run_tests.py --coverage --min-coverage 30
```

Expected coverage: ~32% (meets the 30% minimum)

## Test Files

- `tests/test_database.py` - Database JSONL operations
- `tests/test_helpers_functions.py` - Utility functions
- `tests/test_cli_commands.py` - CLI command integration
- `tests/test_concurrency.py` - File locking and concurrency
- `tests/test_helpers.py` - Test utilities (base classes)

## Current Status

✅ **56/56 tests passing** (100% success rate)
✅ **32.3% code coverage** (exceeds 30% target)
✅ **~2.6 second execution time**
✅ **Zero external dependencies** (stdlib only)

## Troubleshooting

If tests fail, check:
1. Python version 3.x is installed
2. No `.readyq.jsonl` file in tests directory
3. No stale `.readyq.jsonl.lock` files
4. Tests have write permissions in temp directories

#!/usr/bin/env python3
"""
Unified test runner for readyq test suite.

Discovers and runs all tests in the tests/ directory using Python's unittest framework.

Usage:
    python3 run_tests.py                # Run all tests
    python3 run_tests.py -v             # Verbose output
    python3 run_tests.py -k pattern     # Run tests matching pattern
    python3 run_tests.py database       # Run only database tests
    python3 run_tests.py helpers        # Run only helper function tests
    python3 run_tests.py cli            # Run only CLI command tests
    python3 run_tests.py concurrency    # Run only concurrency tests
    python3 run_tests.py --coverage --min-coverage 70  # Run with coverage check
"""

import sys
import os
import unittest
import time
import argparse
from pathlib import Path
import trace


def create_test_suite(test_dir='tests', pattern='test*.py', category=None):
    """
    Create test suite by discovering tests.

    Args:
        test_dir: Root directory for tests
        pattern: Pattern to match test files
        category: Specific category (database, helpers, cli, concurrency)

    Returns:
        unittest.TestSuite
    """
    loader = unittest.TestLoader()

    if category:
        # Map category to specific test file
        category_files = {
            'database': 'test_database.py',
            'helpers': 'test_helpers_functions.py',
            'cli': 'test_cli_commands.py',
            'concurrency': 'test_concurrency.py'
        }
        if category not in category_files:
            print(f"Error: Unknown category '{category}'. Valid categories: {', '.join(category_files.keys())}")
            sys.exit(1)
        pattern = category_files[category]

    # Load all tests
    suite = loader.discover(test_dir, pattern=pattern, top_level_dir='.')

    return suite


def filter_suite_by_pattern(suite, pattern):
    """
    Filter test suite by test name pattern.

    Args:
        suite: unittest.TestSuite
        pattern: String pattern to match in test names

    Returns:
        unittest.TestSuite with filtered tests
    """
    filtered_suite = unittest.TestSuite()

    for test_group in suite:
        if isinstance(test_group, unittest.TestSuite):
            filtered_group = filter_suite_by_pattern(test_group, pattern)
            if filtered_group.countTestCases() > 0:
                filtered_suite.addTest(filtered_group)
        else:
            test_name = str(test_group)
            if pattern.lower() in test_name.lower():
                filtered_suite.addTest(test_group)

    return filtered_suite


def analyze_coverage(tracer, min_coverage=None):
    """
    Analyze coverage results for readyq.py.

    Args:
        tracer: trace.Trace object with coverage data
        min_coverage: Optional minimum coverage percentage

    Returns:
        tuple: (coverage_percent, meets_minimum)
    """
    results = tracer.results()

    # Get coverage for readyq.py only
    readyq_counts = {}
    for filename, lineno in results.counts:
        if filename.endswith('readyq.py'):
            readyq_counts[lineno] = results.counts[(filename, lineno)]

    if not readyq_counts:
        print("\nWarning: No coverage data for readyq.py found")
        return 0.0, False

    # Read readyq.py to count total executable lines
    readyq_path = os.path.join(os.path.dirname(__file__), 'readyq.py')

    with open(readyq_path, 'r') as f:
        lines = f.readlines()

    # Count executable lines (not empty, not comments, not docstrings)
    total_lines = 0
    in_docstring = False
    docstring_delim = None

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Handle docstrings
        if '"""' in stripped or "'''" in stripped:
            if '"""' in stripped:
                delim = '"""'
            else:
                delim = "'''"

            if not in_docstring:
                # Starting docstring
                if stripped.count(delim) >= 2:
                    # Single-line docstring
                    continue
                else:
                    in_docstring = True
                    docstring_delim = delim
                    continue
            else:
                # Ending docstring
                if delim == docstring_delim:
                    in_docstring = False
                    docstring_delim = None
                continue

        if in_docstring:
            continue

        # Skip empty lines and comments
        if not stripped or stripped.startswith('#'):
            continue

        # Count as executable
        total_lines += 1

    executed_lines = len(readyq_counts)
    coverage_percent = (executed_lines / total_lines * 100) if total_lines > 0 else 0

    # Print coverage report
    print()
    print("=" * 70)
    print("Coverage Report")
    print("=" * 70)
    print(f"File: readyq.py")
    print(f"Executable lines: {total_lines}")
    print(f"Executed lines: {executed_lines}")
    print(f"Coverage: {coverage_percent:.1f}%")

    # Check against minimum
    meets_minimum = True
    if min_coverage is not None:
        if coverage_percent < min_coverage:
            print(f"\n✗ Coverage {coverage_percent:.1f}% is below minimum {min_coverage}%")
            meets_minimum = False
        else:
            print(f"\n✓ Coverage {coverage_percent:.1f}% meets minimum {min_coverage}%")

    print("=" * 70)

    return coverage_percent, meets_minimum


def run_tests(verbosity=1, pattern=None, category=None, coverage=False, min_coverage=None):
    """
    Run the test suite.

    Args:
        verbosity: Output verbosity (1=normal, 2=verbose)
        pattern: Optional pattern to filter test names
        category: Optional test category (unit, integration, concurrency)
        coverage: Enable coverage tracking
        min_coverage: Minimum coverage percentage (requires coverage=True)

    Returns:
        tuple: (unittest.TestResult, coverage_percent, meets_minimum)
    """
    # Create test suite
    suite = create_test_suite(category=category)

    # Filter by pattern if provided
    if pattern:
        suite = filter_suite_by_pattern(suite, pattern)
        if suite.countTestCases() == 0:
            print(f"No tests found matching pattern: {pattern}")
            return None, 0.0, False

    # Print test summary
    test_count = suite.countTestCases()
    print("=" * 70)
    print(f"readyq Test Suite")
    print("=" * 70)
    if category:
        print(f"Category: {category}")
    if pattern:
        print(f"Pattern: {pattern}")
    if coverage:
        print(f"Coverage: enabled")
    if min_coverage:
        print(f"Minimum coverage: {min_coverage}%")
    print(f"Tests to run: {test_count}")
    print("=" * 70)
    print()

    # Run tests with optional coverage
    runner = unittest.TextTestRunner(verbosity=verbosity)
    start_time = time.time()

    if coverage:
        # Create tracer
        tracer = trace.Trace(
            count=True,
            trace=False,
            countfuncs=False,
            countcallers=False,
            ignoremods=(),
            ignoredirs=(sys.prefix, sys.exec_prefix),
        )
        result = tracer.runfunc(runner.run, suite)
    else:
        result = runner.run(suite)
        tracer = None

    elapsed_time = time.time() - start_time

    # Print summary
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Time: {elapsed_time:.2f}s")
    print("=" * 70)

    # Analyze coverage if enabled
    coverage_percent = 0.0
    meets_minimum = True
    if coverage and tracer:
        coverage_percent, meets_minimum = analyze_coverage(tracer, min_coverage)

    return result, coverage_percent, meets_minimum


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description='Run readyq test suite',
        epilog='Examples:\n'
               '  python3 run_tests.py\n'
               '  python3 run_tests.py -v\n'
               '  python3 run_tests.py -k "test_lock"\n'
               '  python3 run_tests.py database\n'
               '  python3 run_tests.py cli -v\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'category',
        nargs='?',
        choices=['database', 'helpers', 'cli', 'concurrency', 'all'],
        default='all',
        help='Test category to run (default: all)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.add_argument(
        '-k', '--pattern',
        type=str,
        help='Run only tests matching this pattern'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available tests without running them'
    )

    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Enable coverage tracking (stdlib trace module)'
    )

    parser.add_argument(
        '--min-coverage',
        type=float,
        metavar='PCT',
        help='Minimum coverage percentage required (implies --coverage)'
    )

    args = parser.parse_args()

    # Handle category='all'
    category = None if args.category == 'all' else args.category

    # List tests if requested
    if args.list:
        suite = create_test_suite(category=category)
        if args.pattern:
            suite = filter_suite_by_pattern(suite, args.pattern)

        print(f"Available tests ({suite.countTestCases()}):")
        print("=" * 70)

        def print_tests(test_suite, indent=0):
            for test in test_suite:
                if isinstance(test, unittest.TestSuite):
                    print_tests(test, indent)
                else:
                    print("  " * indent + str(test))

        print_tests(suite)
        return 0

    # Enable coverage if min_coverage specified
    coverage_enabled = args.coverage or args.min_coverage is not None

    # Run tests
    verbosity = 2 if args.verbose else 1
    result, coverage_percent, meets_minimum = run_tests(
        verbosity=verbosity,
        pattern=args.pattern,
        category=category,
        coverage=coverage_enabled,
        min_coverage=args.min_coverage
    )

    if result is None:
        return 1

    # Exit with appropriate code
    success = True
    if not result.wasSuccessful():
        print("\n✗ Some tests failed")
        success = False

    if coverage_enabled and not meets_minimum:
        print("\n✗ Coverage below minimum threshold")
        success = False

    if success:
        print("\n✓ All tests passed!")
        if coverage_enabled:
            print(f"✓ Coverage: {coverage_percent:.1f}%")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())

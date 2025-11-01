"""
Concurrency tests for readyq file locking.

Tests:
- db_lock() context manager
- Lock timeout behavior
- Stale lock cleanup
- Concurrent operations
"""

import os
import time
import threading
import multiprocessing
from tests.test_helpers import TempReadyQTest
import readyq


class TestFileLocking(TempReadyQTest):
    """Test db_lock() context manager."""

    def test_lock_creates_lock_file(self):
        """Test that lock creates .lock file."""
        lock_path = readyq.DB_FILE + '.lock'

        with readyq.db_lock():
            self.assertTrue(os.path.exists(lock_path))

        # Lock should be removed after context
        self.assertFalse(os.path.exists(lock_path))

    def test_lock_file_contains_pid(self):
        """Test that lock file contains process ID."""
        lock_path = readyq.DB_FILE + '.lock'

        with readyq.db_lock():
            with open(lock_path, 'r') as f:
                content = f.read()
                # Should contain a PID (number)
                self.assertTrue(content.strip().isdigit())

    def test_lock_releases_on_exception(self):
        """Test that lock is released even if exception occurs."""
        lock_path = readyq.DB_FILE + '.lock'

        try:
            with readyq.db_lock():
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Lock should be removed even after exception
        self.assertFalse(os.path.exists(lock_path))

    def test_lock_prevents_concurrent_access(self):
        """Test that lock prevents concurrent access to same file."""
        lock_path = readyq.DB_FILE + '.lock'
        results = []

        def try_acquire_lock():
            try:
                with readyq.db_lock(timeout=0.1):
                    results.append("acquired")
            except TimeoutError:
                results.append("timeout")

        # Acquire lock in main thread
        with readyq.db_lock():
            # Try to acquire in another thread (should timeout)
            thread = threading.Thread(target=try_acquire_lock)
            thread.start()
            thread.join()

        # First acquisition succeeded, second timed out
        self.assertEqual(results, ["timeout"])

    def test_lock_can_be_reacquired_after_release(self):
        """Test that lock can be acquired again after release."""
        with readyq.db_lock():
            pass  # First acquisition

        # Should be able to acquire again
        with readyq.db_lock():
            pass  # Second acquisition succeeds

    def test_stale_lock_cleanup(self):
        """Test that stale locks are automatically cleaned up."""
        lock_path = readyq.DB_FILE + '.lock'

        # Create a stale lock file (very old)
        with open(lock_path, 'w') as f:
            f.write("99999\n")

        # Set modification time to 20 seconds ago (2x timeout)
        old_time = time.time() - 20
        os.utime(lock_path, (old_time, old_time))

        # Should be able to acquire lock (stale lock cleaned up)
        with readyq.db_lock(timeout=1.0):
            pass  # Should succeed

    def test_lock_timeout_error(self):
        """Test that lock times out if held too long."""
        def hold_lock():
            with readyq.db_lock(timeout=2.0):
                time.sleep(1.0)  # Hold lock for 1 second

        # Start thread that holds lock
        thread = threading.Thread(target=hold_lock)
        thread.start()
        time.sleep(0.1)  # Give thread time to acquire lock

        # Try to acquire with short timeout
        with self.assertRaises(TimeoutError):
            with readyq.db_lock(timeout=0.2):
                pass

        thread.join()


class TestConcurrentOperations(TempReadyQTest):
    """Test concurrent readyq operations with locking."""

    def test_concurrent_appends_with_locking(self):
        """Test that concurrent appends maintain data integrity."""
        def append_task(task_id):
            task = self.create_task_dict(title=f"Task {task_id}")
            readyq.db_append_task(task)

        # Create multiple threads that append tasks
        threads = []
        for i in range(10):
            thread = threading.Thread(target=append_task, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all tasks were appended
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 10)

    def test_concurrent_save_operations(self):
        """Test that concurrent save operations are serialized."""
        def save_tasks(task_id):
            tasks = []
            for i in range(5):
                task = self.create_task_dict(title=f"Task {task_id}-{i}")
                tasks.append(task)
            readyq.db_save_tasks(tasks)

        # Create multiple threads that save tasks
        threads = []
        for i in range(3):
            thread = threading.Thread(target=save_tasks, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Last save wins - should have 5 tasks from one of the threads
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 5)

    def test_mixed_append_and_save_operations(self):
        """Test that mixed operations maintain consistency."""
        results = []

        def append_operation():
            try:
                for i in range(5):
                    task = self.create_task_dict(title=f"Append {i}")
                    readyq.db_append_task(task)
                results.append("append_success")
            except Exception as e:
                results.append(f"append_error: {e}")

        def save_operation():
            try:
                tasks = [self.create_task_dict(title=f"Save {i}") for i in range(3)]
                readyq.db_save_tasks(tasks)
                results.append("save_success")
            except Exception as e:
                results.append(f"save_error: {e}")

        # Run append and save concurrently
        thread1 = threading.Thread(target=append_operation)
        thread2 = threading.Thread(target=save_operation)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Both operations should succeed
        self.assertIn("append_success", results)
        self.assertIn("save_success", results)

        # Database should be valid
        tasks = readyq.db_load_tasks()
        self.assertGreater(len(tasks), 0)
        self.assertDatabaseValid()


class TestRaceConditionPrevention(TempReadyQTest):
    """Test that locking prevents data races."""

    def test_no_lost_updates(self):
        """Test that concurrent updates don't lose data."""
        # Create initial task
        task = self.create_task_dict(title="Initial task")
        self.save_task(task)

        update_count = [0]

        def update_task():
            tasks = readyq.db_load_tasks()
            tasks[0]['title'] = f"Updated {update_count[0]}"
            update_count[0] += 1
            readyq.db_save_tasks(tasks)

        # Run multiple updates concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_task)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Database should still be valid with one task
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertDatabaseValid()

    def test_no_corrupted_jsonl(self):
        """Test that concurrent writes don't corrupt JSONL format."""
        def rapid_append():
            for i in range(10):
                task = self.create_task_dict(title=f"Task {threading.current_thread().name}-{i}")
                readyq.db_append_task(task)

        # Create multiple threads doing rapid appends
        threads = []
        for i in range(3):
            thread = threading.Thread(target=rapid_append, name=f"Thread{i}")
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Database should be valid JSONL
        self.assertDatabaseValid()

        # Should have all 30 tasks
        tasks = readyq.db_load_tasks()
        self.assertEqual(len(tasks), 30)

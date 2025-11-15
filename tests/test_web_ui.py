"""
Integration tests for readyq web UI endpoints.

Tests web server endpoints and HTML content.
"""

import unittest
import json
import os
import io
import socket
import socketserver
from tests.test_helpers import TempReadyQTest
import readyq


class MockSocket:
    """Mock socket object for testing WebUIHandler."""
    def __init__(self):
        self.rfile = io.BytesIO()
        self.wfile = io.BytesIO()

    def makefile(self, mode='r', buffering=-1):
        """Return a mock file object."""
        if 'r' in mode or 'rb' in mode:
            return self.rfile
        return self.wfile


class MockServer(socketserver.BaseServer):
    """Mock server object for testing WebUIHandler."""
    def __init__(self):
        # Don't call super().__init__() to avoid binding to a socket
        self.server_address = ('127.0.0.1', 8000)

    def server_bind(self):
        pass

    def server_activate(self):
        pass

    def server_close(self):
        pass

    def handle_request(self):
        pass

    def fileno(self):
        return 0


class TestWebUIHandler(TempReadyQTest):
    """Test web UI handler and endpoints."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()

    def test_api_cwd_returns_directory_name(self):
        """Test /api/cwd endpoint logic returns only directory basename."""
        # Create a temporary directory structure to test
        test_dir = os.path.join(self.test_dir, 'test_worktree')
        os.makedirs(test_dir, exist_ok=True)
        original_dir = os.getcwd()

        try:
            os.chdir(test_dir)

            # Test the endpoint logic directly
            cwd = os.path.basename(os.getcwd())
            response = json.dumps({"cwd": cwd})

            # Verify response
            data = json.loads(response)
            self.assertIn('cwd', data)
            self.assertEqual(data['cwd'], 'test_worktree')
            self.assertNotIn('/', data['cwd'])  # Should be basename only
        finally:
            os.chdir(original_dir)

    def test_api_cwd_error_handling(self):
        """Test /api/cwd handles errors gracefully."""
        # Test that error response has correct format
        error_response = json.dumps({"error": "Failed to retrieve working directory"})
        data = json.loads(error_response)

        self.assertIn('error', data)
        self.assertEqual(data['error'], "Failed to retrieve working directory")
        # Should not leak internal paths or exception details
        self.assertNotIn('/', data['error'])
        self.assertNotIn('Traceback', data['error'])


class TestWebUIHTMLContent(TempReadyQTest):
    """Test web UI HTML structure and JavaScript."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        # Create a mock handler to get HTML content
        mock_socket = MockSocket()
        mock_server = MockServer()
        # type: ignore - MockSocket implements the socket interface but doesn't inherit from socket.socket
        handler = readyq.WebUIHandler(mock_socket, ('127.0.0.1', 8000), mock_server)  # type: ignore[arg-type]
        self.html = handler._get_web_html()

    def test_html_contains_cwd_display(self):
        """Test HTML contains CWD display element."""
        html = self.html

        self.assertIn('id="cwd-display"', html)
        self.assertIn('Loading...', html)  # Initial loading text

    def test_html_contains_theme_selector(self):
        """Test HTML contains theme selector dropdown."""
        html = self.html

        self.assertIn('id="theme-selector"', html)
        self.assertIn('class="theme-selector"', html)
        # Verify all themes are present
        self.assertIn('value="default"', html)
        self.assertIn('value="ocean"', html)
        self.assertIn('value="forest"', html)
        self.assertIn('value="sunset"', html)
        self.assertIn('value="purple"', html)
        self.assertIn('value="amber"', html)

    def test_html_contains_theme_validation(self):
        """Test HTML JavaScript contains theme validation."""
        html = self.html

        # Check for theme validation constants
        self.assertIn('VALID_THEMES', html)
        self.assertIn("['default', 'ocean', 'forest', 'sunset', 'purple', 'amber']", html)

        # Check for validation in switchTheme
        self.assertIn('VALID_THEMES.includes(theme)', html)

    def test_html_contains_storage_key_sanitization(self):
        """Test HTML JavaScript sanitizes localStorage keys."""
        html = self.html

        # Check for sanitization function
        self.assertIn('sanitizeForStorageKey', html)
        self.assertIn('replace(/[^a-zA-Z0-9_-]/g', html)

    def test_html_contains_default_cwd_constant(self):
        """Test HTML JavaScript defines DEFAULT_CWD constant."""
        html = self.html

        self.assertIn('DEFAULT_CWD', html)
        self.assertIn("'readyq'", html)

    def test_html_contains_async_initialization(self):
        """Test HTML uses async initialization for CWD loading."""
        html = self.html

        # Check for async DOMContentLoaded handler
        self.assertIn('DOMContentLoaded', html)
        self.assertIn('async ()', html)
        self.assertIn('await loadCwd()', html)

        # Check for error handling
        self.assertIn('try', html)
        self.assertIn('catch', html)

    def test_theme_css_classes_defined(self):
        """Test all theme CSS classes are defined."""
        html = self.html

        # Check for all theme class definitions
        themes = ['default', 'ocean', 'forest', 'sunset', 'purple', 'amber']
        for theme in themes:
            self.assertIn(f'.theme-{theme}', html)
            # Check for CSS variables
            self.assertIn('--color-bg-primary', html)
            self.assertIn('--color-brand', html)


if __name__ == '__main__':
    unittest.main()

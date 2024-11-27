import os
import tempfile
import unittest
from src.log_retrieval_server import LogRetrievalServer


class TestLogRetrievalServer(unittest.TestCase):
    """Test cases for LogRetrievalServer functionality."""

    def setUp(self):
        """Set up test environment using a temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_server = LogRetrievalServer(log_dir=self.temp_dir)
        
        # Create test file
        self.test_filename = 'test_logretrieval.log'
        self.test_log_path = os.path.join(self.temp_dir, self.test_filename)
        
        # Sample log content
        self.test_log_content = [
            "2023-01-01 ERROR: System failure",
            "2023-01-02 INFO: Normal operation",
            "2023-01-03 WARNING: Disk space low"
        ]
        
        with open(self.test_log_path, 'w', encoding='utf-8') as file:
            file.write('\n'.join(self.test_log_content))

    def tearDown(self):
        """Clean up temporary test files."""
        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                try:
                    os.unlink(os.path.join(self.temp_dir, file))
                except OSError:
                    pass
            os.rmdir(self.temp_dir)

    def test_read_log_file(self):
        """Test basic log file reading functionality."""
        logs = self.log_server.read_log_file(self.test_filename)
        self.assertEqual(len(logs), 3, "Should read all log entries")
        
        logs_limited = self.log_server.read_log_file(self.test_filename, lines=2)
        self.assertEqual(len(logs_limited), 2, "Should respect line limit")
        
        logs_filtered = self.log_server.read_log_file(
            self.test_filename, 
            filter_text='ERROR'
        )
        self.assertEqual(len(logs_filtered), 1, "Should filter logs correctly")
        self.assertIn('ERROR', logs_filtered[0], "Filtered log should contain ERROR")

    def test_max_lines_limit(self):
        """Test maximum lines limit functionality."""
        server = LogRetrievalServer(log_dir=self.temp_dir, max_lines=2)
        logs = server.read_log_file(self.test_filename)
        self.assertEqual(
            len(logs), 
            2, 
            "Should respect maximum lines server configuration"
        )

    def test_authentication(self):
        """Test authentication token handling."""
        server = LogRetrievalServer(
            log_dir=self.temp_dir, 
            auth_token="test_token"
        )
        self.assertEqual(
            server.auth_token, 
            "test_token", 
            "Should store authentication token"
        )

    def test_security_checks(self):
        """Test security mechanisms."""
        with self.assertRaises(PermissionError):
            self.log_server.read_log_file('../etc/passwd')
        
        with self.assertRaises(FileNotFoundError):
            self.log_server.read_log_file('nonexistent.log')

    def test_log_content_ordering(self):
        """Test reverse chronological ordering of logs."""
        logs = self.log_server.read_log_file(self.test_filename)
        self.assertIn('2023-01-03', logs[0], "Most recent log should be first")
        self.assertIn('2023-01-01', logs[-1], "Oldest log should be last")

    def test_empty_file_handling(self):
        """Test handling of empty log files."""
        empty_file = os.path.join(self.temp_dir, 'empty.log')
        with open(empty_file, 'w', encoding='utf-8'):
            pass
        
        logs = self.log_server.read_log_file('empty.log')
        self.assertEqual(len(logs), 0, "Should handle empty files gracefully")


if __name__ == '__main__':
    unittest.main()

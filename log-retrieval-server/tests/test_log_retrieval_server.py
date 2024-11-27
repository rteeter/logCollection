import unittest
import os
import tempfile
from src.log_retrieval_server import LogRetrievalServer

class TestLogRetrievalServer(unittest.TestCase):
    def setUp(self):
        """
        Set up test logs directly in /var/log for testing.
        Skip tests if we don't have permission.
        """
        self.log_server = LogRetrievalServer()
        
        # Create test file in /var/log if we have permission
        try:
            self.test_filename = 'test_logretrieval.log'
            self.test_log_path = os.path.join('/var/log', self.test_filename)
            
            # Create sample log content
            test_log_content = [
                "2023-01-01 ERROR: System failure",
                "2023-01-02 INFO: Normal operation",
                "2023-01-03 WARNING: Disk space low"
            ]
            
            with open(self.test_log_path, 'w') as f:
                f.write('\n'.join(test_log_content))
                
        except PermissionError:
            self.skipTest("Need root/sudo access to write to /var/log")
    
    def tearDown(self):
        """Clean up test files"""
        try:
            if hasattr(self, 'test_log_path') and os.path.exists(self.test_log_path):
                os.remove(self.test_log_path)
        except PermissionError:
            pass  # Ignore cleanup errors
    
    def test_read_log_file(self):
        """Test log file reading functionality"""
        # Test basic retrieval
        logs = self.log_server.read_log_file(self.test_filename)
        self.assertEqual(len(logs), 3)
        
        # Test line limit
        logs_limited = self.log_server.read_log_file(self.test_filename, lines=2)
        self.assertEqual(len(logs_limited), 2)
        
        # Test filtering
        logs_filtered = self.log_server.read_log_file(self.test_filename, filter_text='ERROR')
        self.assertEqual(len(logs_filtered), 1)
        self.assertTrue('ERROR' in logs_filtered[0])

    def test_security_checks(self):
        """Test security mechanisms"""
        # Test directory traversal prevention
        with self.assertRaises(PermissionError):
            self.log_server.read_log_file('../etc/passwd')
        
        # Test non-existent file
        with self.assertRaises(FileNotFoundError):
            self.log_server.read_log_file('nonexistent.log')

    def test_serve_ui(self):
        """Test serving the web UI"""
        with self.assertRaises(Exception) as context:
            self.log_server.serve_ui()
        
        # Ensure the UI template exists
        template_path = os.path.join(
            os.path.dirname(__file__),
            '../src/templates/index.html'
        )
        self.assertTrue(os.path.exists(template_path))
        
    def test_routes(self):
        """Test URL routing"""
        # Test root route (UI)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-type'], 'text/html')
        
        # Test logs route (API)
        response = self.client.get('/logs?filename=test.log')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-type'], 'application/json')

if __name__ == '__main__':
    unittest.main()

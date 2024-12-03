import unittest
import os
import tempfile
import time
import random
import string
import json
from http.client import HTTPConnection
from threading import Thread
from unittest.mock import patch, MagicMock
import psutil
from http.server import HTTPServer

from src.log_retrieval_server import LogRetrievalServer, create_server, LogRequestHandler

class TestLogRetrievalServer(unittest.TestCase):
    """
    Test suite for the Log Retrieval Server.

    A note on the test naming:
    I renamed these tests using a security station metaphor to help me think through
    what each test is actually doing. While the main code is all about log files and
    HTTP requests, thinking about it like a security guard accessing security footage
    helped me visualize the access patterns better:

    - A server is like a guard station (accepts requests, checks credentials)
    - Auth tokens are like security badges (you need the right one to get in)
    - Log files are like security footage (you're looking through past events)
    - Log directory is like a security room (you can only access what's inside)

    This mental model helped me write more focused tests and made edge cases more 
    obvious - like what happens when someone tries to access files outside the permitted
    area (directory traversal) or uses an invalid badge (auth token).

    The actual implementation stays clean and technical - this is just a testing 
    pattern that helped me think through the security aspects of the system.
    """

    @classmethod
    def setUpClass(cls):
        """Set up the test log room"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.base_port = 8888
    
    def setUp(self):
        """Prepare the guard station for each test"""
        self.server = LogRetrievalServer()
        self.patcher = patch.object(self.server, 'log_dir', self.temp_dir)
        self.patcher.start()
        
    def tearDown(self):
        """Clean up the guard station after each test"""
        self.patcher.stop()
        # Clean up test logs
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
            
    @classmethod
    def tearDownClass(cls):
        """Close down the test log room"""
        os.rmdir(cls.temp_dir)

    def create_test_log(self, filename, content):
        """Create a test log file in the secure log room
        
        Args:
            filename (str): Name of the security log file
            content (str): Log entries to record
        
        Returns:
            str: Full path to the secured log file
        """
        path = os.path.join(self.temp_dir, filename)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def create_guard_station(self, port, security_badge=None):
        """Set up a new guard station for monitoring logs
        
        Args:
            port (int): Guard station communication port
            security_badge (str, optional): Security badge for authentication
            
        Returns:
            tuple: (station, thread) - The guard station and its monitoring thread
        """
        # Create a server directly instead of using create_server helper
        server_address = ('', port)
        station = HTTPServer(server_address, LogRequestHandler)
        
        # Create and configure the log retriever with the test directory
        log_retriever = LogRetrievalServer(auth_token=security_badge)
        log_retriever.log_dir = self.temp_dir  # Directly set the log directory
        
        # Attach the configured log retriever to the server
        station.log_retriever = log_retriever
        station.auth_token = security_badge
        
        # Start the server
        monitor_thread = Thread(target=station.serve_forever)
        monitor_thread.daemon = True
        monitor_thread.start()
        time.sleep(0.1)  # Allow station to initialize
        
        return station, monitor_thread

    def test_guard_can_read_basic_log(self):
        """Verify guards can read basic security logs"""
        log_entries = "\n".join(f"Security Event {i}" for i in range(10))
        self.create_test_log("security_feed.log", log_entries)
        
        result = self.server.read_log_file("security_feed.log", lines=5)
        
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], "Security Event 9")
        self.assertEqual(result[-1], "Security Event 5")

    def test_guard_receives_error_for_nonexistent_log(self):
        """Verify proper error when requesting non-existent security footage"""
        with self.assertRaises(FileNotFoundError):
            self.server.read_log_file("missing_camera.log")

    def test_prevent_access_outside_log_room(self):
        """Verify prevention of unauthorized access outside secure log room"""
        with self.assertRaises(PermissionError):
            self.server.read_log_file("../../../etc/passwd")

    def test_guard_can_filter_incident_reports(self):
        """Verify guards can filter logs for specific security incidents"""
        incidents = "\n".join([
            "ALERT: Unauthorized access detected",
            "INFO: Routine patrol completed",
            "ALERT: Motion sensor triggered",
            "DEBUG: System check normal"
        ])
        self.create_test_log("incidents.log", incidents)
        
        result = self.server.read_log_file("incidents.log", filter_text="ALERT")
        
        self.assertEqual(len(result), 2)
        self.assertTrue(all("ALERT" in line for line in result))

    def test_enforce_max_report_length(self):
        """Verify enforcement of maximum security report length"""
        long_report = "\n".join(f"Security Event {i}" for i in range(2000))
        self.create_test_log("long_report.log", long_report)
        
        server = LogRetrievalServer(max_lines=1000)
        with patch.object(server, 'log_dir', self.temp_dir):
            result = server.read_log_file("long_report.log")
            self.assertEqual(len(result), 1000)

    def test_security_badge_system(self):
        """Verify the security badge access control system"""
        security_badge = "test_badge"
        port = self.base_port
        
        # Create and verify test file before starting server
        log_path = self.create_test_log("access_log.log", "Security checkpoint entry\n")
        self.assertTrue(os.path.exists(log_path), "Test log file was not created")
        
        station, thread = self.create_guard_station(port, security_badge)
        
        try:
            # Verify the server's log directory is correctly set
            self.assertEqual(station.log_retriever.log_dir, self.temp_dir, 
                        f"Server log directory mismatch. Expected {self.temp_dir}, got {station.log_retriever.log_dir}")
            
            conn = HTTPConnection(f"localhost:{port}")
            
            # Test with valid security badge
            headers = {"Authorization": f"Bearer {security_badge}"}
            conn.request("GET", "/logs?filename=access_log.log", headers=headers)
            response = conn.getresponse()
            response_body = response.read().decode()
            
            self.assertEqual(response.status, 200, 
                        f"Guard station returned error: {response_body}")
            response_data = json.loads(response_body)
            self.assertIn('entries', response_data)
            
            # Test with counterfeit security badge
            headers = {"Authorization": "Bearer fake_badge"}
            conn.request("GET", "/logs?filename=access_log.log", headers=headers)
            response = conn.getresponse()
            response_body = response.read()  # Read the response body first
            
            self.assertEqual(response.status, 401, 
                            f"Expected 401 status, got {response.status}")
            
            # Only try to parse JSON if there's content
            if response_body:
                try:
                    response_data = json.loads(response_body.decode())
                    self.assertIn('error', response_data)
                except json.JSONDecodeError:
                    self.fail(f"Invalid JSON in error response: {response_body.decode()}")
            
        finally:
            station.shutdown()
            station.server_close()
            thread.join(timeout=1)

    def test_log_room_security_protocols(self):
        """Verify all security protocols for log room access"""
        security_badge = "test_badge"
        port = self.base_port + 1
        
        station, thread = self.create_guard_station(port, security_badge)
        
        try:
            conn = HTTPConnection(f"localhost:{port}")
            headers = {"Authorization": f"Bearer {security_badge}"}
            
            # Test missing log file designation
            conn.request("GET", "/logs", headers=headers)
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            response.read()  # Clear security check
            
            # Test invalid request format (malformed lines parameter)
            conn.request("GET", "/logs?filename=test.log&lines=invalid", headers=headers)
            response = conn.getresponse()
            self.assertEqual(response.status, 400)  # Changed from 500 to 400 as it's an invalid parameter
            response.read()  # Clear security check
            
            # Test unauthorized area access attempt
            conn.request("GET", "/logs?filename=../../../etc/passwd", headers=headers)
            response = conn.getresponse()
            self.assertEqual(response.status, 403)  # Changed from 500 to 403 as it's a permissions issue
            response.read()  # Clear security check
            
        finally:
            station.shutdown()
            station.server_close()
            thread.join(timeout=1)

    def test_log_room_handles_massive_archive(self):
        """Verify efficient handling of massive security footage archive"""
        filename = "massive_archive.log"
        file_size = 1024 * 1024 * 1024  # 1GB archive
        chunk_size = 1024 * 1024  # Process in 1MB chunks
        
        path = os.path.join(self.temp_dir, filename)
        
        print("\nGenerating 1GB security archive...")
        with open(path, 'w') as f:
            bytes_written = 0
            while bytes_written < file_size:
                chunk = ''.join(
                    f"[{int(time.time())}] CAMERA_{random.randint(1,10)}: " + 
                    f"SECTOR_{random.choice(['A','B','C','D'])} " +
                    f"ACTIVITY_LEVEL_{random.choice(['LOW', 'MEDIUM', 'HIGH'])}: " + 
                    ''.join(random.choices(string.ascii_letters + string.digits, k=50)) + 
                    "\n" for _ in range(1000)
                )
                f.write(chunk)
                bytes_written += len(chunk.encode())
                if bytes_written % (100 * 1024 * 1024) == 0:
                    print(f"Archived {bytes_written / (1024*1024):.0f}MB of footage...")
                    
        print("Archive generated. Testing retrieval speed...")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        start_time = time.time()
        result = self.server.read_log_file(filename, lines=1000)
        end_time = time.time()
        
        final_memory = process.memory_info().rss
        memory_used = (final_memory - initial_memory) / (1024 * 1024)
        
        print(f"\nRetrieval Performance Metrics:")
        print(f"Access time: {end_time - start_time:.2f} seconds")
        print(f"Memory usage: {memory_used:.2f} MB")
        print(f"Footage entries retrieved: {len(result)}")
        
        self.assertLess(end_time - start_time, 5.0, "Archive access too slow")
        self.assertLess(memory_used, 100, "Memory usage exceeded security limits")
        self.assertEqual(len(result), 1000, "Incorrect number of footage entries retrieved")

if __name__ == '__main__':
    unittest.main()

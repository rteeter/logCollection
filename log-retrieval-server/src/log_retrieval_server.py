#!/usr/bin/env python3
import os
import json
import re
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import List, Optional
import argparse
import base64

class LogRetrievalServer:
    """
    A minimal, dependency-light log retrieval server for Unix-based systems.
    
    Core Features:
    - REST API for log file retrieval
    - Minimal external dependencies
    - Secure, configurable log access
    """
    
    def __init__(self, auth_token: Optional[str] = None, max_lines: int = 1000):
        """
        Initialize the log retrieval server.
        
        Args:
            auth_token (str, optional): Authentication token
            max_lines (int): Maximum number of log lines to return
        """
        self.log_dir = '/var/log'  # Hard-coded to /var/log
        self.auth_token = auth_token
        self.max_lines = max_lines
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def read_log_file(self, filename, lines=None, filter_text=None):
        """
        Read log file with advanced filtering and pagination.

        Args:
            filename (str): Log file name
            lines (int, optional): Number of lines to return
            filter_text (str, optional): Text to filter log entries

        Returns:
            List[str]: Filtered and paginated log entries
        """
        full_path = os.path.join(self.log_dir, filename)

        # Security: Prevent directory traversal
        if not os.path.abspath(full_path).startswith(os.path.abspath(self.log_dir)):
            raise PermissionError(f"Invalid file path: {filename}")

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Log file not found: {filename}")

        try:
            with open(full_path, 'r') as f:
                # Read lines in reverse, most recent first
                all_lines = f.readlines()[::-1]

                # Apply filtering
                if filter_text:
                    all_lines = [
                        line for line in all_lines
                        if re.search(filter_text, line, re.IGNORECASE)
                    ]

                # Limit lines
                lines = lines or self.max_lines
                return all_lines[:lines]

        except PermissionError:
            self.logger.error(f"Permission denied reading {filename}")
            return []
        except Exception as e:
            self.logger.error(f"Error reading log file: {e}")
            return []

class LogRequestHandler(BaseHTTPRequestHandler):
    """
    Custom HTTP Request Handler for Log Retrieval
    """
    
    def do_GET(self):
        """
        Handle GET requests for log retrieval
        """
        # Parse URL and query parameters
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        
        try:
            # Authentication check if token is configured
            if hasattr(self.server, 'auth_token') and self.server.auth_token:
                auth_header = self.headers.get('Authorization')
                if not auth_header or not auth_header.startswith('Bearer '):
                    self.send_error(401, "Authorization header missing or invalid")
                    return
                token = auth_header.split(' ')[1]
                if token != self.server.auth_token:
                    self.send_error(401, "Invalid token")
                    return

            # Validate path
            if parsed_path.path != '/logs':
                self.send_error(404, "Not Found")
                return
            
            # Extract query parameters
            filename = params.get('filename', [None])[0]
            lines = int(params.get('lines', [1000])[0])
            filter_text = params.get('filter', [None])[0]
            
            # Validate parameters
            if not filename:
                self.send_error(400, "Filename is required")
                return
            
            # Retrieve log entries
            log_retriever = self.server.log_retriever
            log_entries = log_retriever.read_log_file(
                filename, 
                lines=lines, 
                filter_text=filter_text
            )
            
            # Prepare response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                'filename': filename,
                'total_entries': len(log_entries),
                'entries': log_entries
            }
            
            self.wfile.write(json.dumps(response).encode())
        
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {str(e)}")

def create_server(
    port: int = 8000, 
    auth_token: Optional[str] = None
):
    """
    Create and configure the log retrieval server.
    
    Args:
        port (int): Server listening port
        auth_token (str, optional): Authentication token
    
    Returns:
        HTTPServer: Configured HTTP server instance
    """
    log_retriever = LogRetrievalServer(auth_token=auth_token)
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, LogRequestHandler)
    httpd.log_retriever = log_retriever
    httpd.auth_token = auth_token
    
    return httpd

def main():
    """
    Main entry point for the log retrieval server
    """
    parser = argparse.ArgumentParser(
        description='Minimal Log Retrieval Server'
    )
    parser.add_argument(
        '-p', '--port', 
        type=int, 
        default=8000, 
        help='Port to listen on'
    )
    parser.add_argument(
        '-t', '--token', 
        help='Authentication token'
    )
    
    args = parser.parse_args()
    
    try:            
        httpd = create_server(
            port=args.port, 
            auth_token=args.token
        )
        print(f"Serving logs from /var/log on port {args.port}")
        if args.token:
            print("Authentication enabled")
            
        httpd.serve_forever()
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

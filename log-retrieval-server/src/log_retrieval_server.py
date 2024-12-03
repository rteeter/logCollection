#!/usr/bin/env python3
import os
import json
import re
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional
import argparse

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
        
        # Validate log directory
        if not os.path.isdir(self.log_dir):
            raise ValueError(f"Invalid log directory: {self.log_dir}")
        
    def read_log_file(self, filename, lines=None, filter_text=None):
        """
        Read log file with efficient filtering and pagination.
        Reads file in chunks from the end to handle large files.

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

        lines_wanted = lines or self.max_lines
        matching_lines = []
        
        try:
            with open(full_path, 'rb') as f:
                # Start from end of file
                f.seek(0, os.SEEK_END)
                pos = f.tell()
                
                # Read chunks from end of file
                chunk_size = 8192  # 8KB chunks
                leftovers = ''
                
                while pos > 0 and len(matching_lines) < lines_wanted:
                    # Move back by chunk size
                    chunk_end = pos
                    pos = max(pos - chunk_size, 0)
                    f.seek(pos)
                    
                    # Read chunk and decode
                    chunk = f.read(chunk_end - pos)
                    text = chunk.decode('utf-8', errors='ignore')
                    
                    # Split into lines and handle partial lines
                    chunk_lines = text.splitlines()
                    
                    if leftovers:
                        chunk_lines[-1] = chunk_lines[-1] + leftovers
                    if pos > 0:
                        leftovers = chunk_lines[0]
                        chunk_lines = chunk_lines[1:]
                    
                    # Process lines in reverse
                    for line in reversed(chunk_lines):
                        if filter_text and filter_text not in line:
                            continue
                        matching_lines.append(line)
                        if len(matching_lines) >= lines_wanted:
                            break

            return matching_lines

        except Exception as e:
            print(f"Error reading log file: {e}")
            raise

class LogRequestHandler(BaseHTTPRequestHandler):
    """
    Custom HTTP Request Handler for Log Retrieval
    """
    
    def send_error_json(self, code: int, message: str):
        """Send an error response in JSON format"""
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "error": message
        }).encode())

    def do_GET(self):
        """Handle GET requests for log retrieval and web UI"""
        parsed_path = urlparse(self.path)
        
        # Serve web UI at root
        if parsed_path.path == '/':
            self.serve_ui()
            return
            
        # Handle API requests
        elif parsed_path.path == '/logs':
            params = parse_qs(parsed_path.query)
            
            try:
                # Authentication check
                auth_header = self.headers.get('Authorization')
                if hasattr(self.server, 'auth_token') and self.server.auth_token:
                    if not auth_header or not auth_header.startswith('Bearer '):
                        self.send_error_json(401, "Authorization header missing or invalid")
                        return
                    token = auth_header.split(' ')[1]
                    if token != self.server.auth_token:
                        self.send_error_json(401, "Invalid token")
                        return

                # Extract query parameters
                filename = params.get('filename', [None])[0]
                if not filename:
                    self.send_error_json(400, "Filename is required")
                    return
                
                try:
                    lines = int(params.get('lines', ['1000'])[0])
                except ValueError:
                    self.send_error_json(400, "Invalid lines parameter")
                    return
                    
                filter_text = params.get('filter', [None])[0]
                
                try:
                    log_entries = self.server.log_retriever.read_log_file(
                        filename, 
                        lines=lines, 
                        filter_text=filter_text
                    )
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    self.wfile.write(json.dumps({
                        'filename': filename,
                        'total_entries': len(log_entries),
                        'entries': log_entries
                    }).encode())
                    
                except FileNotFoundError:
                    self.send_error_json(404, f"Log file not found: {filename}")
                except PermissionError:
                    self.send_error_json(403, "Access to file path denied")
                except Exception as e:
                    self.send_error_json(500, f"Internal server error: {str(e)}")
                    
            except Exception as e:
                self.send_error_json(500, f"Internal server error: {str(e)}")
                
        else:
            self.send_error_json(404, "Not Found")

    def serve_ui(self):
        """Serve the web UI"""
        template_path = os.path.join(
            os.path.dirname(__file__), 
            'templates', 
            'index.html'
        )
        try:
            with open(template_path, 'r') as f:
                html = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(html.encode())
        except Exception as e:
            self.send_error_json(500, f"Error serving UI: {str(e)}")

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

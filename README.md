# Log Retrieval Server

## Overview
A minimal, secure, and lightweight log retrieval server for Unix-based systems, providing both REST API and web interface access to log files from /var/log. Built with only Python standard library dependencies, it supports authentication, filtering, and configurable line limits.

## Features
- Minimal Python standard library dependencies
- Secure log file access
- Flexible log retrieval options (filtering, line limits)
- Authentication support
- Web UI for easy log access

## Requirements
- Python 3.8+
- Unix-like operating system
- Read access to /var/log directory (may require sudo)

## Installation
```bash
# Clone the repository
git clone git@github.com:rteeter/logCollection.git
cd logCollection/log-retrieval-server
```

## Usage

### Running the Server
```bash
# Basic usage
python src/log_retrieval_server.py

# Specify custom port
python src/log_retrieval_server.py -p 9000

# Add authentication
python src/log_retrieval_server.py -t mysecrettoken
```

### API Endpoints

#### GET /logs
Retrieve log entries with flexible filtering

**Query Parameters:**
- `filename`: (Required) Name of the log file
- `lines`: Number of recent log entries to retrieve (default: 1000)
- `filter`: Keyword to filter log entries

**Response Format:**
```json
{
    "filename": "system.log",
    "total_entries": 100,
    "entries": [
        "2024-01-01 INFO: Log entry 1",
        "2023-12-31 ERROR: Log entry 2",
        ...
    ]
}
```

**Example Requests:**
```bash
# Get last 100 lines from system log
curl "http://localhost:8000/logs?filename=system.log&lines=100"

# Filter system log for Configuration entries
curl "http://localhost:8000/logs?filename=system.log&filter=Configuration"

# With authentication if enabled
curl -H "Authorization: Bearer mysecrettoken" "http://localhost:8000/logs?filename=system.log"
```

## Web Interface
A basic web interface is available for demonstrating the log retrieval functionality:

1. Access the UI by opening `http://localhost:8000/` in your browser
2. Enter the authentication token if required
3. Specify the log file name (e.g., system.log)
4. Optionally set the number of lines and filter text
5. Click "Retrieve Logs" to view the results

Example:
```bash
# Start the server with authentication
python src/log_retrieval_server.py -t mysecrettoken

# Then open in browser:
http://localhost:8000/
```

## Security Considerations
- Restricts file access to specified log directory
- Optional token-based authentication
- Input validation and sanitization
- Directory traversal prevention

## Testing

### Unit Tests
```bash
python -m unittest tests/test_log_retrieval_server.py
```

Test coverage includes:
- Basic log file reading and filtering
- Line limit enforcement
- Authentication token handling
- Security checks (directory traversal prevention)
- Log ordering verification
- Empty file handling
- Error cases

### Manual Testing
1. Start the server:
```bash
python src/log_retrieval_server.py -t mysecrettoken
```

2. Test basic functionality:
```bash
# Test authentication
curl -H "Authorization: Bearer mysecrettoken" \
     "http://localhost:8000/logs?filename=system.log"

# Test line limiting
curl "http://localhost:8000/logs?filename=system.log&lines=10"

# Test filtering
curl "http://localhost:8000/logs?filename=system.log&filter=ERROR"
```

3. Test web interface:
- Open `http://localhost:8000` in browser
- Enter authentication token
- Try various log files and filters

## Limitations
- Requires root/sudo for full `/var/log` access
- No built-in rate limiting
- Basic authentication mechanism

## Potential Improvements
- Add more robust authentication
- Implement rate limiting
- Support for compressed log files
- Add request logging and monitoring

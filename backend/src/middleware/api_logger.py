"""
API Request Logging Middleware
Logs all API requests and responses for monitoring and debugging
"""

import logging
import time
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Callable
from datetime import datetime
import os

# Create dedicated API logger
api_logger = logging.getLogger("api_requests")
api_logger.setLevel(logging.INFO)

# Create logs directory if it doesn't exist
# Use relative path to work both locally and in Docker
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# Create file handler for API logs
api_log_file = os.path.join(log_dir, "api_requests.log")
file_handler = logging.FileHandler(api_log_file)
file_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)

# Add handler to logger
if not api_logger.handlers:
    api_logger.addHandler(file_handler)


class APILoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests and responses"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details"""

        # Start timer
        start_time = time.time()

        # Extract request details
        method = request.method
        url = str(request.url)
        client_ip = request.client.host if request.client else "unknown"

        # Skip logging for certain paths (to reduce noise)
        skip_paths = ["/health", "/docs", "/openapi.json", "/favicon.ico"]
        if any(url.endswith(path) for path in skip_paths):
            return await call_next(request)

        # Process request
        response = None
        status_code = 500  # Default to error
        error_msg = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            error_msg = str(e)
            api_logger.error(
                f"{method} {url} - ERROR: {error_msg} - IP: {client_ip}"
            )
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time
            duration_ms = round(duration * 1000, 2)

            # Determine log level based on status code
            if status_code >= 500:
                log_level = "ERROR"
            elif status_code >= 400:
                log_level = "WARNING"
            else:
                log_level = "INFO"

            # Format log message
            log_message = (
                f"{method} {url} - "
                f"Status: {status_code} - "
                f"Duration: {duration_ms}ms - "
                f"IP: {client_ip}"
            )

            # Log to API logger
            if log_level == "ERROR":
                api_logger.error(log_message)
            elif log_level == "WARNING":
                api_logger.warning(log_message)
            else:
                api_logger.info(log_message)

        return response


def setup_api_logging(app):
    """Setup API logging middleware"""
    app.add_middleware(APILoggingMiddleware)
    api_logger.info("API logging middleware initialized")

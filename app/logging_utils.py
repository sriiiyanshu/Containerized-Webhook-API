"""
Structured JSON logging configuration for the application.
Outputs one JSON object per line with standardized fields.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from contextvars import ContextVar

from fastapi import Request


# Context variable to store request ID across async operations
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON objects.
    
    Each log line is a single JSON object with the following keys:
    - ts: ISO-8601 timestamp
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - request_id: Request ID if available
    - message: Log message
    - Additional fields for HTTP requests (method, path, status, latency_ms)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        # Add HTTP request specific fields if present
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add any extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure application-wide structured JSON logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Remove all existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    
    # Configure root logger
    root_logger.setLevel(log_level.upper())
    root_logger.addHandler(console_handler)
    
    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Logger instance configured for structured JSON logging
    """
    return logging.getLogger(name)


class RequestLogger:
    """
    Middleware helper for logging HTTP requests with structured JSON format.
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize request logger.
        
        Args:
            logger: Logger instance to use for logging
        """
        self.logger = logger
    
    def log_request(
        self,
        request: Request,
        status_code: int,
        latency_ms: float,
        request_id: str
    ) -> None:
        """
        Log HTTP request with structured fields.
        
        Args:
            request: FastAPI Request object
            status_code: HTTP response status code
            latency_ms: Request processing time in milliseconds
            request_id: Unique request identifier
        """
        # Set request ID in context
        request_id_var.set(request_id)
        
        # Create log record with extra fields
        self.logger.info(
            f"{request.method} {request.url.path} {status_code} {latency_ms:.2f}ms",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": round(latency_ms, 2),
            }
        )


async def log_request_middleware(request: Request, call_next):
    """
    FastAPI middleware to log all HTTP requests with structured JSON format.
    
    Args:
        request: Incoming HTTP request
        call_next: Next middleware or route handler
    
    Returns:
        HTTP response
    """
    import uuid
    
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    
    # Store start time
    start_time = time.time()
    
    # Process request
    try:
        response = await call_next(request)
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Log request
        logger = get_logger("api")
        logger.info(
            f"{request.method} {request.url.path} {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": round(latency_ms, 2),
            }
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
    
    except Exception as exc:
        # Calculate latency even for errors
        latency_ms = (time.time() - start_time) * 1000
        
        # Log error
        logger = get_logger("api")
        logger.error(
            f"{request.method} {request.url.path} 500",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "latency_ms": round(latency_ms, 2),
            },
            exc_info=True
        )
        
        raise
    finally:
        # Clear request ID from context
        request_id_var.set(None)

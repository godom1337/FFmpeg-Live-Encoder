"""Error handling middleware"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import traceback
from typing import Any, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware:
    """Middleware for centralized error handling"""

    async def __call__(self, request: Request, call_next):
        """Process request and handle errors

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response or error response
        """
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            return await self.handle_error(request, e)

    async def handle_error(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle different types of errors

        Args:
            request: Request that caused the error
            exc: Exception that was raised

        Returns:
            JSONResponse: Formatted error response
        """
        error_id = f"ERR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        # Log the error
        logger.error(
            f"Error {error_id} on {request.method} {request.url.path}: {exc}",
            exc_info=True
        )

        # Handle different error types
        if isinstance(exc, HTTPException):
            return await self.handle_http_exception(exc, error_id)
        elif isinstance(exc, RequestValidationError):
            return await self.handle_validation_error(exc, error_id)
        else:
            return await self.handle_generic_error(exc, error_id)

    async def handle_http_exception(
        self,
        exc: HTTPException,
        error_id: str
    ) -> JSONResponse:
        """Handle HTTP exceptions

        Args:
            exc: HTTP exception
            error_id: Error identifier

        Returns:
            JSONResponse: Error response
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "id": error_id,
                    "type": "http_error",
                    "status": exc.status_code,
                    "message": exc.detail,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

    async def handle_validation_error(
        self,
        exc: RequestValidationError,
        error_id: str
    ) -> JSONResponse:
        """Handle validation errors

        Args:
            exc: Validation error
            error_id: Error identifier

        Returns:
            JSONResponse: Error response with validation details
        """
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "id": error_id,
                    "type": "validation_error",
                    "status": 422,
                    "message": "Request validation failed",
                    "validation_errors": errors,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

    async def handle_generic_error(
        self,
        exc: Exception,
        error_id: str
    ) -> JSONResponse:
        """Handle generic/unexpected errors

        Args:
            exc: Generic exception
            error_id: Error identifier

        Returns:
            JSONResponse: Error response
        """
        # In production, don't expose internal error details
        debug_mode = logger.isEnabledFor(logging.DEBUG)

        error_detail = {
            "id": error_id,
            "type": "internal_error",
            "status": 500,
            "message": "An internal server error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }

        if debug_mode:
            # Include stack trace in debug mode
            error_detail["debug"] = {
                "exception": str(exc),
                "traceback": traceback.format_exc()
            }

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": error_detail}
        )

def create_error_handlers(app):
    """Register error handlers with FastAPI app

    Args:
        app: FastAPI application instance
    """
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle Starlette HTTP exceptions"""
        error_id = f"ERR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.warning(f"HTTP {exc.status_code} error {error_id}: {exc.detail}")

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "id": error_id,
                    "type": "http_error",
                    "status": exc.status_code,
                    "message": exc.detail or "HTTP error occurred",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors"""
        error_id = f"ERR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.warning(f"Validation error {error_id} on {request.url.path}")

        errors = []
        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"][1:])  # Skip first element (usually "body")
            errors.append({
                "field": field_path or "request",
                "message": error["msg"],
                "type": error["type"]
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "id": error_id,
                    "type": "validation_error",
                    "status": 422,
                    "message": "Request validation failed",
                    "validation_errors": errors,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle value errors"""
        error_id = f"ERR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.warning(f"Value error {error_id}: {exc}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "id": error_id,
                    "type": "bad_request",
                    "status": 400,
                    "message": str(exc),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions"""
        error_id = f"ERR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.error(
            f"Unhandled error {error_id} on {request.method} {request.url.path}",
            exc_info=exc
        )

        # Don't expose internal errors in production
        debug_mode = logger.isEnabledFor(logging.DEBUG)

        error_detail = {
            "id": error_id,
            "type": "internal_error",
            "status": 500,
            "message": "An internal server error occurred. Please try again later.",
            "timestamp": datetime.utcnow().isoformat()
        }

        if debug_mode:
            error_detail["debug"] = {
                "exception": str(exc),
                "type": type(exc).__name__
            }

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": error_detail}
        )
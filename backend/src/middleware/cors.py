"""CORS middleware configuration"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
import logging

logger = logging.getLogger(__name__)

def setup_cors(
    app: FastAPI,
    allowed_origins: Optional[List[str]] = None,
    allow_credentials: bool = True,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None
) -> None:
    """Configure CORS middleware for the application

    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origins
        allow_credentials: Whether to allow credentials
        allow_methods: List of allowed HTTP methods
        allow_headers: List of allowed headers
    """
    # Get origins from environment or use defaults
    if allowed_origins is None:
        env_origins = os.getenv("CORS_ORIGINS", "")
        if env_origins:
            allowed_origins = [origin.strip() for origin in env_origins.split(",")]
        else:
            # Default origins for development
            allowed_origins = [
                "http://localhost",
                "http://localhost:80",
                "http://localhost:3000",
                "http://localhost:5173",  # Vite dev server
                "http://localhost:8000",
                "http://127.0.0.1",
                "http://127.0.0.1:80",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:8000",
            ]

            # Add container hostname if running in Docker
            container_hostname = os.getenv("HOSTNAME")
            if container_hostname:
                allowed_origins.extend([
                    f"http://{container_hostname}",
                    f"http://{container_hostname}:80",
                    f"http://{container_hostname}:8000"
                ])

    # Default allowed methods
    if allow_methods is None:
        allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]

    # Default allowed headers
    if allow_headers is None:
        allow_headers = [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Request-ID",
            "X-API-Key",
        ]

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        expose_headers=[
            "X-Total-Count",
            "X-Page",
            "X-Page-Size",
            "X-Request-ID"
        ],
        max_age=3600  # Cache preflight requests for 1 hour
    )

    logger.info(f"CORS configured with origins: {allowed_origins}")

def get_cors_config() -> dict:
    """Get current CORS configuration

    Returns:
        dict: CORS configuration settings
    """
    env_origins = os.getenv("CORS_ORIGINS", "")
    if env_origins:
        origins = [origin.strip() for origin in env_origins.split(",")]
    else:
        origins = ["http://localhost:*", "http://127.0.0.1:*"]

    return {
        "allowed_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["*"],
        "max_age": 3600
    }
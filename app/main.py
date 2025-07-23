"""
Customer Support Intelligence API - Main Application Module.

This module contains the main FastAPI application instance with configuration
for CORS, exception handling, lifespan management, and API routing.

The application provides AI-powered classification and routing of customer
support tickets using OpenAI's API with fallback classification logic.

Author: Customer Support Intelligence Team
Version: 1.0.0
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.endpoints import requests, stats
from app.config import settings
from app.database import async_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles application startup and shutdown events including database
    connection testing and resource cleanup.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Yields control during application runtime.

    Note:
        This function runs at application startup and shutdown, managing
        database connections and performing health checks.
    """
    # Application startup phase
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")

    # Test database connection on startup
    try:
        from sqlalchemy import text

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")

    # Yield control to the application runtime
    yield

    # Application shutdown phase
    print("Shutting down application")
    await async_engine.dispose()


# Create the main FastAPI application instance
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered customer support ticket automation API",
    lifespan=lifespan,  # Application lifespan manager
    # Conditionally enable API documentation based on environment
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Configure Cross-Origin Resource Sharing (CORS) middleware
# Only add CORS middleware if origins are specified in configuration
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.cors_origins],
        allow_credentials=True,  # Allow cookies and authentication headers
        allow_methods=["*"],  # Allow all HTTP methods
        allow_headers=["*"],  # Allow all headers
    )


# Global exception handlers for standardized error responses


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Custom exception handler for Pydantic validation errors.

    Transforms FastAPI's default validation error responses into a more
    user-friendly format by extracting field names, error messages, and
    error types from the exception details.

    Args:
        request (Request): The incoming HTTP request that caused the error.
        exc (RequestValidationError): The validation exception containing
            detailed error information.

    Returns:
        JSONResponse: A formatted JSON response with structured error details
            and HTTP 422 status code.

    Note:
        This handler processes multiple validation errors and formats them
        into a consistent structure for client consumption.
    """
    errors = []
    # Process each validation error in the exception
    for error in exc.errors():
        # Extract field path (excluding 'body' from the location tuple)
        field = " -> ".join(str(x) for x in error["loc"][1:])
        errors.append(
            {
                "field": field,  # Field that failed validation
                "message": error["msg"],  # Human-readable error message
                "type": error["type"],  # Error type identifier
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    General exception handler for unhandled server errors.

    Catches all uncaught exceptions and provides appropriate error responses
    based on the application environment. In production, it returns generic
    error messages to avoid exposing sensitive information, while in
    development it provides detailed error information for debugging.

    Args:
        request (Request): The HTTP request that triggered the exception.
        exc (Exception): The unhandled exception that was raised.

    Returns:
        JSONResponse: A JSON error response with HTTP 500 status code.

    Note:
        In production environments, actual error details are hidden from
        clients but should be logged for monitoring and debugging purposes.
    """
    # Determine error message based on environment
    # Production: Generic message to avoid information disclosure
    # Development: Detailed error for debugging
    error_message = "Internal server error" if settings.is_production else str(exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_message},
    )


# Application health and information endpoints


@app.get("/", include_in_schema=False)
async def root() -> Dict[str, Any]:
    """
    Root endpoint providing basic application information.

    This endpoint serves as a simple health check and information provider,
    returning basic application metadata. It's excluded from OpenAPI schema
    to keep the documentation clean.

    Returns:
        Dict[str, Any]: Application status and metadata including name,
            version, and environment information.

    Note:
        This endpoint is typically used by load balancers and monitoring
        systems for basic health verification.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/health", tags=["monitoring"])
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint for service monitoring.

    Performs health checks on critical application dependencies including
    database connectivity and external services. Returns detailed status
    information for each component to help with monitoring and alerting.

    Returns:
        Dict[str, Any]: Detailed health status including overall application
            status and individual service statuses.

    Note:
        This endpoint is designed for use by monitoring systems like
        Kubernetes health probes, load balancers, and application monitoring
        tools. A "degraded" status indicates partial functionality.
    """
    # Test database connectivity
    db_status = "healthy"
    try:
        from sqlalchemy import text

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Determine overall application status
    overall_status = "healthy" if db_status == "healthy" else "degraded"

    return {
        "status": overall_status,
        "services": {
            "database": db_status,
            # TODO: Implement actual AI service check
            "ai_classifier": "healthy",
        },
    }


# API Router Registration
# Register all API endpoint routers with the main application

app.include_router(
    requests.router,
    prefix=settings.api_v1_prefix,  # Add versioned API prefix (e.g., /api/v1)
)
app.include_router(
    stats.router,
    prefix=settings.api_v1_prefix,  # Add versioned API prefix (e.g., /api/v1)
)


# Optional: Prometheus metrics endpoint for monitoring
# Uncomment the following lines to enable Prometheus metrics collection
# This provides detailed application metrics for monitoring and alerting
#
# from prometheus_client import make_asgi_app
# metrics_app = make_asgi_app()
# app.mount("/metrics", metrics_app)


# Application entry point for direct execution
if __name__ == "__main__":
    """
    Direct execution entry point for development purposes.

    When this module is run directly (python -m app.main), it starts
    the Uvicorn ASGI server with development-friendly settings including
    auto-reload and appropriate logging levels.

    Note:
        For production deployments, use a dedicated ASGI server like
        Uvicorn, Gunicorn with Uvicorn workers, or similar production-ready
        servers instead of this direct execution method.
    """
    import uvicorn

    # Start the ASGI server with environment-specific configuration
    uvicorn.run(
        "app.main:app",  # Application import string
        host="0.0.0.0",  # Bind to all interfaces
        port=8000,  # Default port
        reload=settings.is_development,  # Enable auto-reload in dev
        log_level=settings.log_level.lower(),  # Use configured log level
    )

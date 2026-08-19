"""
Radia AI — FastAPI application factory.

This module creates and configures the FastAPI application instance. It wires:
  - CORS middleware
  - request ID middleware (injects X-Request-ID and binds it to structlog context)
  - global exception handlers (translate domain exceptions to JSON error responses)
  - API versioned router
  - OpenAPI metadata

It deliberately contains NO business logic — that lives in services/.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.exceptions import RadiaBaseException
from app.core.logging import configure_logging, get_logger
from app.dependencies.container import lifespan
from app.schemas.common import ErrorDetail, ErrorResponse
from app.utils.request_id import generate_request_id, set_request_id

# Initialise logging before anything else so all startup messages are structured
settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


def create_app() -> FastAPI:
    """
    Application factory — returns a fully configured FastAPI instance.

    Using a factory function (instead of a module-level app = FastAPI())
    makes it trivial to create isolated test instances with different settings.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Radia AI is an enterprise Retrieval-Augmented Generation platform "
            "that answers engineering questions grounded in indexed documents."
        ),
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url="/api/redoc" if settings.environment != "production" else None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    return app


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


def _register_middleware(app: FastAPI) -> None:
    """Attach all middleware to the application in correct order (outermost first)."""

    # CORS — must be outermost so preflight OPTIONS requests are handled correctly
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_and_timing_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        Per-request middleware that:
          1. Reads or generates a request ID (X-Request-ID header)
          2. Binds the request ID to structlog context variables so all logs
             from this request automatically include it
          3. Measures total request duration and logs it
          4. Echos the request ID in the response header
        """
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        set_request_id(request_id)

        # Make request_id available on request.state for endpoint handlers
        request.state.request_id = request_id

        import structlog

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "http_request",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )

        return response


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers that convert exceptions to JSON."""

    @app.exception_handler(RadiaBaseException)
    async def radia_exception_handler(
        request: Request, exc: RadiaBaseException
    ) -> JSONResponse:
        """Map domain exceptions to standardized JSON error responses."""
        logger.warning(
            "domain_exception",
            error_code=exc.error_code,
            message=exc.message,
            detail=exc.detail,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=exc.error_code,
                    message=exc.message,
                    detail=exc.detail,
                ),
                request_id=getattr(request.state, "request_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Convert Pydantic validation errors to a consistent error envelope."""
        errors = exc.errors()
        logger.info("validation_error", error_count=len(errors))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    detail={"errors": errors},
                ),
                request_id=getattr(request.state, "request_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Catch-all for unexpected exceptions.

        Logs the full traceback internally but returns a generic message to the
        caller — never expose stack traces in production responses.
        """
        logger.exception("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred. Please try again later.",
                ),
                request_id=getattr(request.state, "request_id", ""),
            ).model_dump(),
        )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------


def _register_routers(app: FastAPI) -> None:
    """Mount versioned API routers."""
    app.include_router(v1_router, prefix=settings.api_prefix)


# ---------------------------------------------------------------------------
# Application instance — used by uvicorn
# ---------------------------------------------------------------------------

app = create_app()

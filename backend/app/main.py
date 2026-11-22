import logging
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import log_structured, request_id_ctx
from app.core.security import CSRF_HEADER_NAME


@asynccontextmanager
async def lifespan(_: FastAPI):
    issues = settings.validate_production_readiness()
    if issues and settings.is_production:
        log_structured(
            logging.CRITICAL,
            "startup.production_config_invalid",
            category="startup",
            details={"violations": issues},
        )
        raise RuntimeError(f"Unsafe production configuration: {'; '.join(issues)}")
    yield


def create_application() -> FastAPI:
    show_docs = not ((settings.is_production or settings.is_staging) and not settings.DEBUG)
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.2.0",
        description="DIGI-VERSE Digital Products E-Commerce Platform API",
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
        lifespan=lifespan,
    )

    if settings.ALLOWED_HOSTS and "*" not in settings.ALLOWED_HOSTS:
        application.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=list(settings.ALLOWED_HOSTS),
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", CSRF_HEADER_NAME, "X-Request-ID", "Accept"],
        expose_headers=[CSRF_HEADER_NAME, "X-Request-ID", "Content-Disposition", "Content-Length"],
    )

    @application.middleware("http")
    async def request_context_and_security_middleware(request: Request, call_next) -> Response:
        req_id = (request.headers.get("X-Request-ID") or "").strip()[:64] or uuid.uuid4().hex
        token = request_id_ctx.set(req_id)
        try:
            is_asset_upload = request.method.upper() == "POST" and bool(
                re.match(r"^/api/admin/products/[0-9a-fA-F-]+/asset/?$", request.url.path)
            )
            max_body_bytes = (
                max(settings.MAX_REQUEST_BODY_BYTES, settings.MAX_ASSET_UPLOAD_BYTES + (2 * 1024 * 1024))
                if is_asset_upload
                else settings.MAX_REQUEST_BODY_BYTES
            )
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > max_body_bytes:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "detail": "Request payload exceeds maximum permitted size.",
                                "request_id": req_id,
                            },
                            headers={"X-Request-ID": req_id},
                        )
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length header.", "request_id": req_id},
                        headers={"X-Request-ID": req_id},
                    )

            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if settings.COOKIE_SECURE or settings.is_production:
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
            return response
        finally:
            request_id_ctx.reset(token)

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = request_id_ctx.get() or uuid.uuid4().hex
        log_structured(
            logging.ERROR,
            "http.unhandled_exception",
            category="error",
            details={
                "method": request.method,
                "path": request.url.path,
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected internal server error occurred.",
                "request_id": req_id,
            },
            headers={"X-Request-ID": req_id},
        )

    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return application


app = create_application()

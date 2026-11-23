from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.routes import (
    admin_auth,
    admin_catalog,
    admin_operations,
    admin_orders,
    auth,
    commerce,
    public_catalog,
    seller,
    webhooks,
)
from app.api.routes.financial import admin_financial_router, seller_financial_router
from app.api.routes.payout import (
    admin_payout_account_router,
    admin_payout_router,
    seller_payout_router,
)
from app.core.config import settings
from app.core.database import check_database_connection

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin_auth.router)
api_router.include_router(admin_catalog.router)
api_router.include_router(admin_orders.router)
api_router.include_router(admin_operations.router)
api_router.include_router(commerce.router)
api_router.include_router(public_catalog.router)
api_router.include_router(seller.router)
api_router.include_router(seller.admin_seller_router)
api_router.include_router(webhooks.router)
api_router.include_router(seller_financial_router)
api_router.include_router(admin_financial_router)
api_router.include_router(seller_payout_router)
api_router.include_router(admin_payout_router)
api_router.include_router(admin_payout_account_router)


@api_router.get("/health", tags=["Health"])
def health_check() -> JSONResponse:
    """Liveness + real database connectivity check (executes `SELECT 1`).

    Returns 200 when the database is reachable, otherwise 503 with status "degraded".
    Defined as a sync endpoint so the blocking DB round-trip runs in FastAPI's threadpool.
    """
    db_connected, db_error = check_database_connection()
    payload = {
        "application": settings.PROJECT_NAME,
        "status": "healthy" if db_connected else "degraded",
        "database": {
            "status": "connected" if db_connected else "disconnected",
            # Only the exception class is exposed, never connection strings or credentials.
            "error": db_error,
        },
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=200 if db_connected else 503, content=payload)


@api_router.get("/ready", tags=["Health"])
def readiness_check() -> JSONResponse:
    """Dependency readiness check verifying database connectivity and deployed config safety."""
    db_connected, db_error = check_database_connection()
    if settings.is_staging:
        config_issues = settings.validate_staging_readiness()
    else:
        config_issues = settings.validate_production_readiness()
    is_ready = bool(db_connected and not config_issues)
    payload = {
        "application": settings.PROJECT_NAME,
        "status": "ready" if is_ready else "not_ready",
        "checks": {
            "database": "ok" if db_connected else (db_error or "unreachable"),
            "configuration": "ok" if not config_issues else "invalid",
        },
        "capabilities": {
            "payments": settings.get_payment_provider_state(),
            "email": settings.get_email_provider_state(),
            "whatsapp": settings.get_whatsapp_provider_state(),
            "asset_storage": settings.get_asset_storage_state(),
            "image_storage": settings.get_image_storage_state(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=200 if is_ready else 503, content=payload)

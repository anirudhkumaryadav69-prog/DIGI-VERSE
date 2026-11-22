"""Delivery status webhook routes for Resend (Email) and Meta Cloud API (WhatsApp)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.webhook_service import (
    process_email_webhook,
    process_whatsapp_webhook,
    verify_whatsapp_webhook_challenge,
)

router = APIRouter(prefix="/webhooks", tags=["Delivery Webhooks"])


@router.post("/email")
async def email_delivery_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    raw_body = await request.body()
    res = process_email_webhook(
        db,
        raw_body=raw_body,
        svix_id=request.headers.get("svix-id"),
        svix_timestamp=request.headers.get("svix-timestamp"),
        svix_signature=request.headers.get("svix-signature"),
    )
    db.commit()
    return res


@router.get("/whatsapp", response_class=PlainTextResponse)
def whatsapp_webhook_verify(
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    challenge = verify_whatsapp_webhook_challenge(
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge,
    )
    return PlainTextResponse(content=challenge, status_code=200)


@router.post("/whatsapp")
async def whatsapp_delivery_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    raw_body = await request.body()
    res = process_whatsapp_webhook(
        db,
        raw_body=raw_body,
        signature_header=request.headers.get("X-Hub-Signature-256"),
    )
    db.commit()
    return res

"""
Health check and a few operational endpoints.
Admin endpoints are guarded with a simple header token so you can trigger
the daily summary from curl without exposing it publicly.
"""
from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException

from ..config import get_settings
from ..services import daily_summary, db

router = APIRouter(tags=["ops"])


@router.get("/")
async def root():
    return {"service": "kirana-bookkeeper", "status": "ok"}


@router.get("/healthz")
async def healthz():
    settings = get_settings()
    missing = settings.assert_ready_for_runtime()
    return {
        "ok": len(missing) == 0,
        "missing_config": missing,
        "env": settings.app_env,
    }


@router.post("/admin/run-daily-summary")
async def trigger_daily_summary(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """Run the daily summary batch. Protect with WHATSAPP_WEBHOOK_VERIFY_TOKEN
    (re-used here for simplicity — there is no other user-facing use for it)."""
    settings = get_settings()
    if x_admin_token != settings.whatsapp_webhook_verify_token:
        raise HTTPException(status_code=401, detail="unauthorized")
    sent = await daily_summary.run_daily_summary_for_all()
    return {"sent": sent}


@router.get("/admin/shop/{phone}/summary")
async def get_shop_summary(
    phone: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    settings = get_settings()
    if x_admin_token != settings.whatsapp_webhook_verify_token:
        raise HTTPException(status_code=401, detail="unauthorized")
    if not phone.startswith("+"):
        phone = "+" + phone
    sk = await db.get_or_create_shopkeeper(phone)
    text = await daily_summary.build_daily_summary_text(sk)
    return {"shopkeeper_id": str(sk["id"]), "summary": text}

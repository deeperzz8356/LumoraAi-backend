from fastapi import APIRouter, Header, HTTPException, Request
from app.services.billing_service import billing_service
from app.core.config import get_settings

router = APIRouter()


@router.post("/revenuecat")
async def revenuecat_webhook(request: Request, authorization: str = Header(None)):
    settings = get_settings()
    auth_key = settings.revenuecat_webhook_auth_key

    if auth_key:
        expected = f"Bearer {auth_key}"
        if not authorization or authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized webhook request")

    payload = await request.json()
    try:
        result = billing_service.handle_revenuecat_event(payload)
        return {"status": "success", "data": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

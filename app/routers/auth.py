from fastapi import APIRouter, HTTPException, Depends
from app.core.security import get_current_user
from app.services.auth_service import verify_and_sync_user
from pydantic import BaseModel

router = APIRouter()

class SyncUserRequest(BaseModel):
    id_token: str

@router.post("/sync")
async def sync_user_route(body: SyncUserRequest):
    """
    Syncs a user from frontend to backend.
    The frontend should call this after any successful Firebase login (Google, Guest, Email)
    and pass the Firebase ID token in the body.
    """
    try:
        result = await verify_and_sync_user(body.id_token)
        return {"status": "success", "user": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid Firebase ID Token")


@router.get("/me")
async def get_my_profile(user: dict = Depends(get_current_user)):
    """
    Protected endpoint to verify Firebase Token and get current user details.
    Requires a valid Firebase ID Token in the Authorization header: `Bearer <token>`
    """
    return {
        "message": "Token verified successfully! This is official Firebase Auth.",
        "uid": user.get("uid"),
        "email": user.get("email"),
        "firebase_details": user
    }

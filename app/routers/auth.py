from fastapi import APIRouter
from app.schemas.auth import AuthResponse, LoginRequest, GuestLoginRequest
from app.services.auth_service import login, guest_login

router = APIRouter()


@router.post("/login", response_model=AuthResponse)
async def login_route(body: LoginRequest):
    result = await login(body.email, body.password)
    return AuthResponse(access_token=result["access_token"], user_id=result["user_id"])


@router.post("/guest", response_model=AuthResponse)
async def guest_login_route(body: GuestLoginRequest):
    result = await guest_login(body.device_id)
    return AuthResponse(access_token=result["access_token"], user_id=result["user_id"])

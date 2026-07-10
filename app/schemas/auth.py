from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class GuestLoginRequest(BaseModel):
    device_id: str | None = None


class GoogleLoginRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    status: str = "success"
    access_token: str
    user_id: str
    token_type: str = "Bearer"

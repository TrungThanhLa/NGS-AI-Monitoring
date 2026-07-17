from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    full_name: str | None = None
    email: str | None = None
    status: str
    is_active: bool
    phone: str | None = None
    avatar_url: str | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    roles: list[str]
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserResponse

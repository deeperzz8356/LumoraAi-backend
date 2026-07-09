from pydantic import BaseModel
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    status: str = "success"
    data: T


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    code: str | None = None


class PublicListResponse(BaseModel):
    status: str = "success"
    items: list[dict[str, Any]]

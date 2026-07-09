from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    style: str | None = None


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    model: str | None = None
    duration: int = 5
    aspect_ratio: str = "9:16"


class JobResponse(BaseModel):
    status: str = "success"
    jobId: str
    queuePosition: int = 1
    progress: int = 0

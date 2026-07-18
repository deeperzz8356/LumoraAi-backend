from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    style: str | None = None


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    model: str | None = None
    duration: int = 10
    aspect_ratio: str = "16:9"
    source_image_b64: str | None = None
    motion_strength: int = 65
    camera_direction: str | None = None


class JobResponse(BaseModel):
    status: str = "success"
    jobId: str
    queuePosition: int = 1
    progress: int = 0

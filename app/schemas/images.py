from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    negative_prompt: str | None = Field(default=None, max_length=500)
    model: str | None = None
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    steps: int | None = Field(default=None, ge=1, le=50)
    seed: int | None = Field(default=None, ge=0)
    style: str | None = Field(default=None, max_length=100)
    source_image_b64: str | None = None


class ImageGenerateResponse(BaseModel):
    status: str = "success"
    jobId: str
    queuePosition: int = 1
    progress: int = 100
    model: str
    imageUrl: str
    mimeType: str = "image/svg+xml"

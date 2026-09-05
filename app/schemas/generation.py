from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    style: str | None = None


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    model: str | None = None
    duration: int = 10
    aspect_ratio: str = "16:9"
    # Bugs 3 & 5 (isBugCondition3/5): the UI-selected style must reach the
    # backend and be mapped through to the Vertex request. The client sends the
    # style label (e.g. "Anime") and omits it (None) when the default/unstyled
    # option is selected, so the default output is preserved (req 3.13).
    style: str | None = Field(default=None, max_length=100)
    source_image_b64: str | None = None
    motion_strength: int = 65
    camera_direction: str | None = None


class JobResponse(BaseModel):
    status: str = "success"
    jobId: str
    queuePosition: int = 1
    progress: int = 0

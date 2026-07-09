from __future__ import annotations

from app.database.fake_store import store
from app.providers.cloudflare_provider import CloudflareProvider, encode_data_url
from app.schemas.images import ImageGenerateRequest


provider = CloudflareProvider()


async def generate_text_to_image(user_id: str, payload: ImageGenerateRequest) -> dict:
    artifact = await provider.generate_image(payload)
    image_url = encode_data_url(artifact.image_bytes, artifact.mime_type)
    job = store.create_job(
        user_id,
        "image",
        payload.model_dump(),
        result_url=image_url,
    )
    job["model"] = artifact.model
    job["mimeType"] = artifact.mime_type
    job["imageUrl"] = image_url
    return job

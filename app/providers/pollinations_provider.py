import base64
import urllib.parse
import httpx
from app.core.config import get_settings
from app.schemas.images import ImageGenerateRequest
from app.services.ai_provider import GeneratedImage

class PollinationsProvider:
    async def generate_image(self, request: ImageGenerateRequest) -> GeneratedImage:
        settings = get_settings()
        
        encoded_prompt = urllib.parse.quote(request.prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        
        params = {
            "width": request.width,
            "height": request.height,
            "nologo": "true",
            "enhance": "false",
        }
        
        if request.seed is not None:
            params["seed"] = request.seed
            
        headers = {}
        if settings.pollinations_api_key:
            headers["Authorization"] = f"Bearer {settings.pollinations_api_key}"

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            image_bytes = response.content
            mime_type = response.headers.get("Content-Type", "image/jpeg")
            
        return GeneratedImage(
            image_bytes=image_bytes, 
            mime_type=mime_type, 
            model="pollinations"
        )

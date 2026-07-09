from __future__ import annotations

import base64
import json
from html import escape

import httpx

from app.core.config import get_settings
from app.schemas.images import ImageGenerateRequest
from app.services.ai_provider import GeneratedImage


class CloudflareProvider:
    async def generate_image(self, request: ImageGenerateRequest) -> GeneratedImage:
        settings = get_settings()
        model = request.model or settings.workers_ai_model

        if not settings.cloudflare_api_token or not settings.cloudflare_account_id:
            image_bytes = self._render_placeholder_svg(request.prompt, request.style)
            return GeneratedImage(image_bytes=image_bytes, mime_type="image/svg+xml", model=model)

        payload, is_multipart = self._build_request_payload(request, model)
        url = f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/run/{model}"

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            if is_multipart:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
                    files=payload,
                )
            else:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.cloudflare_api_token}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(payload),
                )

        response.raise_for_status()
        body = response.json()

        if not body.get("success", True):
            raise RuntimeError(f"Cloudflare Workers AI error: {body}")

        result = body.get("result")
        image_bytes, mime_type = self._decode_image_result(result)
        return GeneratedImage(image_bytes=image_bytes, mime_type=mime_type, model=model)

    def _build_request_payload(self, request: ImageGenerateRequest, model: str) -> tuple[dict, bool]:
        if model.startswith("@cf/black-forest-labs/flux-2"):
            files: dict[str, tuple[None, str]] = {
                "prompt": (None, request.prompt),
                "width": (None, str(request.width)),
                "height": (None, str(request.height)),
            }
            if request.steps is not None:
                files["steps"] = (None, str(request.steps))
            if request.seed is not None:
                files["seed"] = (None, str(request.seed))
            if request.negative_prompt:
                files["negative_prompt"] = (None, request.negative_prompt)
            return files, True

        payload: dict[str, object] = {"prompt": request.prompt}
        if request.steps is not None:
            payload["steps"] = request.steps
        if request.seed is not None:
            payload["seed"] = request.seed
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt
        return payload, False

    def _decode_image_result(self, result: object) -> tuple[bytes, str]:
        if isinstance(result, str):
            return self._decode_base64_image(result), self._infer_mime_type(result)
        if isinstance(result, dict):
            image_value = result.get("image") if isinstance(result.get("image"), str) else None
            if image_value:
                return self._decode_base64_image(image_value), self._infer_mime_type(image_value)
        raise RuntimeError(f"Unsupported Cloudflare Workers AI result shape: {type(result)!r}")

    def _decode_base64_image(self, image_value: str) -> bytes:
        if "," in image_value and image_value.startswith("data:"):
            image_value = image_value.split(",", 1)[1]
        return base64.b64decode(image_value)

    def _infer_mime_type(self, image_value: str) -> str:
        if image_value.startswith("data:image/png"):
            return "image/png"
        if image_value.startswith("data:image/webp"):
            return "image/webp"
        return "image/jpeg"

    def _render_placeholder_svg(self, prompt: str, style: str | None) -> bytes:
        safe_prompt = escape(prompt[:160])
        safe_style = escape(style or "default")
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='1024' height='1024' viewBox='0 0 1024 1024'>
  <defs>
    <linearGradient id='bg' x1='0%' y1='0%' x2='100%' y2='100%'>
      <stop offset='0%' stop-color='#101828'/>
      <stop offset='100%' stop-color='#2dd4bf'/>
    </linearGradient>
  </defs>
  <rect width='1024' height='1024' fill='url(#bg)'/>
  <rect x='72' y='72' width='880' height='880' rx='40' fill='rgba(255,255,255,0.08)' stroke='rgba(255,255,255,0.2)'/>
  <text x='120' y='210' fill='#f8fafc' font-size='56' font-family='Arial, Helvetica, sans-serif' font-weight='700'>Lumora AI</text>
  <text x='120' y='300' fill='#d1fae5' font-size='34' font-family='Arial, Helvetica, sans-serif'>Text to Image Preview</text>
  <text x='120' y='420' fill='#ffffff' font-size='30' font-family='Arial, Helvetica, sans-serif'>Prompt</text>
  <text x='120' y='470' fill='#e2e8f0' font-size='28' font-family='Arial, Helvetica, sans-serif'>{safe_prompt}</text>
  <text x='120' y='590' fill='#ffffff' font-size='30' font-family='Arial, Helvetica, sans-serif'>Style</text>
  <text x='120' y='640' fill='#e2e8f0' font-size='28' font-family='Arial, Helvetica, sans-serif'>{safe_style}</text>
</svg>"""
        return svg.encode("utf-8")


def encode_data_url(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"

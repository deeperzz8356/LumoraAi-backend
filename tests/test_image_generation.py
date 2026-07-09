from fastapi.testclient import TestClient

from app.main import app
from app.services.image_service import provider
from app.services.ai_provider import GeneratedImage


client = TestClient(app)


def test_image_generation_route():
    async def fake_generate_image(request):
        return GeneratedImage(
            image_bytes=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            mime_type="image/svg+xml",
            model="@cf/black-forest-labs/flux-1-schnell",
        )

    provider.generate_image = fake_generate_image  # type: ignore[method-assign]

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "a neon fox running through a rainy cyberpunk street", "style": "cinematic"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["jobId"]
    assert payload["model"]
    assert payload["imageUrl"].startswith("data:image/svg+xml;base64,")

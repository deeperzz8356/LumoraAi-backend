from app.database.firestore_repositories.credit_repo import credit_repo
from app.database.firestore_repositories.analytics_repo import analytics_repo
from app.providers.cloudflare_provider import CloudflareProvider, encode_data_url
from app.providers.pollinations_provider import PollinationsProvider
from app.schemas.images import ImageGenerateRequest
import random

cloudflare_provider = CloudflareProvider()
pollinations_provider = PollinationsProvider()

async def generate_image(user_id: str, payload: dict) -> dict:
    # 1. Check & Deduct Credits
    if not credit_repo.deduct_credits(user_id, amount=1):
        raise ValueError("Insufficient credits to generate image")

    # 2. Process Request & Template (Style)
    request_obj = ImageGenerateRequest(**payload)
    if request_obj.style:
        request_obj.prompt = f"{request_obj.prompt}, in {request_obj.style} style"

    # 3. Load Balance between Providers
    providers = ["cloudflare", "pollinations"]
    chosen_provider_name = random.choice(providers)
    
    if chosen_provider_name == "pollinations":
        generated = await pollinations_provider.generate_image(request_obj)
    else:
        generated = await cloudflare_provider.generate_image(request_obj)
        
    # 4. Log Analytics (History metadata)
    analytics_repo.log_generation(
        user_id=user_id,
        feature=f"text_to_image_style_{request_obj.style}" if request_obj.style else "text_to_image",
        provider=chosen_provider_name,
        prompt=request_obj.prompt
    )
    
    # 5. Encode image to Base64 data URL for local-first Android return
    base64_url = encode_data_url(generated.image_bytes, generated.mime_type)

    return {
        "status": "success",
        "image_url": base64_url, 
        "model": generated.model,
        "provider": chosen_provider_name
    }

async def generate_video(user_id: str, payload: dict) -> dict:
    # Future Pixzalo Video Provider integration goes here
    if not credit_repo.deduct_credits(user_id, amount=5):
        raise ValueError("Insufficient credits to generate video")
        
    return {
        "status": "pending",
        "message": "Video generation using multiple APIs will be implemented here."
    }

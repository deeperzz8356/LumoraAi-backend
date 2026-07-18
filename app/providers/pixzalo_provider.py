import httpx
import os
import asyncio

class PixzaloProvider:
    def __init__(self):
        # Allow the user to specify their API key in the environment or on Render
        self.api_key = os.getenv("PIXZALO_API_KEY", "")
        # The user can update this URL once they confirm the exact API endpoint
        self.api_url = os.getenv("PIXZALO_API_URL", "https://api.pixzalo.ai/v1/video/create")

    async def generate_video(self, payload: dict) -> dict:
        prompt = payload.get("prompt", "A cinematic scene")
        engine = payload.get("model", "default")
        duration = payload.get("duration", 10)
        motion_strength = payload.get("motion_strength", 65)
        camera_direction = payload.get("camera_direction")
        source_image = payload.get("source_image_b64")
        
        # If no API key is provided, we return a mock response so the frontend still works
        # until the user configures their Render dashboard with the actual API key.
        if not self.api_key:
            await asyncio.sleep(3) # Simulate processing time
            return {
                "status": "success",
                "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "model": engine,
                "provider": "pixzalo-mock"
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        request_data = {
            "prompt": prompt,
            "model": "create", # The user requested the "create" model
            "parameters": {
                "engine": engine,
                "duration": duration,
                "motion": motion_strength
            }
        }
        
        if camera_direction:
            request_data["parameters"]["camera"] = camera_direction
            
        if source_image:
            request_data["image"] = source_image

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(self.api_url, json=request_data, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # We assume the API returns a video_url. 
                # If it's asynchronous (Task ID), this logic will need to poll a GET endpoint.
                video_url = data.get("video_url") or data.get("url") or data.get("output")
                
                if video_url:
                    return {
                        "status": "success",
                        "video_url": video_url,
                        "model": engine,
                        "provider": "pixzalo"
                    }
                else:
                    return {
                        "status": "error",
                        "message": "API succeeded but did not return a video URL."
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Pixzalo API Error: {str(e)}"
                }

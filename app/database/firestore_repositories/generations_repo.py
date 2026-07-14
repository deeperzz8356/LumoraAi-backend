from google.cloud import firestore
from app.core.firebase import get_firestore_client
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class GenerationsRepository:
    def __init__(self):
        self.collection_name = "generations"

    def get_collection(self):
        db = get_firestore_client()
        return db.collection(self.collection_name)

    def find_cached_image(self, prompt: str, style: str = None) -> str | None:
        """Find an existing generated image by prompt and style to save API costs."""
        try:
            query = self.get_collection().where(filter=firestore.FieldFilter("prompt", "==", prompt))
            if style:
                query = query.where(filter=firestore.FieldFilter("style", "==", style))
            
            docs = query.limit(1).stream()
            for doc in docs:
                data = doc.to_dict()
                return data.get("image_url")
        except Exception as e:
            logger.error(f"Error finding cached generation: {e}")
        return None

    def save_generation(self, user_id: str, prompt: str, style: str, image_url: str, provider: str, model: str):
        """Save a new generation to Firestore for tracking and future caching."""
        try:
            doc_ref = self.get_collection().document()
            doc_ref.set({
                "user_id": user_id,
                "prompt": prompt,
                "style": style,
                "image_url": image_url,
                "provider": provider,
                "model": model,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            return doc_ref.id
        except Exception as e:
            logger.error(f"Error saving generation metadata: {e}")
            return None

    def get_user_generations(self, user_id: str, limit: int = 20) -> list:
        """Fetch the most recent generations for a specific user."""
        try:
            query = self.get_collection().where(
                filter=firestore.FieldFilter("user_id", "==", user_id)
            ).order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
            
            docs = query.stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                # Remove non-serializable datetime before returning
                if "created_at" in data:
                    data["created_at"] = data["created_at"].isoformat() if data["created_at"] else None
                results.append(data)
            return results
        except Exception as e:
            logger.error(f"Error fetching user generations: {e}")
            return []

generations_repo = GenerationsRepository()

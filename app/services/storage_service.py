from app.core.firebase import get_storage_bucket
import uuid
import datetime
import logging

logger = logging.getLogger(__name__)

class StorageService:
    def upload_image(self, user_id: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str | None:
        """Uploads an image to Firebase Cloud Storage and returns the public URL."""
        try:
            bucket = get_storage_bucket()
            if not bucket:
                logger.error("Firebase Storage bucket is not configured.")
                return None
                
            # Create a unique filename
            extension = "png" if "png" in mime_type else "jpg"
            filename = f"users/{user_id}/generations/{uuid.uuid4()}.{extension}"
            
            blob = bucket.blob(filename)
            blob.upload_from_string(image_bytes, content_type=mime_type)
            
            # Make the blob publicly accessible
            blob.make_public()
            return blob.public_url
        except Exception as e:
            logger.error(f"Error uploading image to storage: {e}")
            return None

storage_service = StorageService()

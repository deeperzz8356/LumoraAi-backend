from typing import Any
import datetime
from app.core.firebase import get_firestore_client

class AnalyticsRepository:
    def __init__(self):
        self.collection_name = "generation_analytics"
        self.db = get_firestore_client()

    def log_generation(self, user_id: str, feature: str, provider: str, prompt: str) -> str:
        if self.db is None:
            return "" # Graceful degradation if Firestore is not initialized
            
        doc_ref = self.db.collection(self.collection_name).document()
        doc_ref.set({
            "user_id": user_id,
            "feature": feature,
            "provider": provider,
            "prompt": prompt,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        return doc_ref.id

analytics_repo = AnalyticsRepository()

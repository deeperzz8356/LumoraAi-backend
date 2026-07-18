from typing import Dict, Any
from app.core.firebase import get_firestore_client
from datetime import datetime, timezone

class UserRepository:
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = self.db.collection("users")

    def ensure_user(self, user_id: str, email: str = None) -> None:
        user_ref = self.collection.document(user_id)
        doc = user_ref.get()
        if not doc.exists:
            user_ref.set({
                "id": user_id,
                "email": email or f"{user_id}@demo.local",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            })

    def get_user(self, user_id: str) -> Dict[str, Any]:
        user_ref = self.collection.document(user_id)
        doc = user_ref.get()
        if doc.exists:
            return doc.to_dict()
        return {}

user_repo = UserRepository()

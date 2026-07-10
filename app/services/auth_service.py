from app.database.firestore_repositories.user_repo import user_repo
from firebase_admin import auth


async def verify_and_sync_user(id_token: str) -> dict:
    """
    Verifies the actual Firebase ID token provided by the frontend.
    Syncs the user in the backend database.
    """
    if not id_token:
        raise ValueError("ID Token cannot be empty")
    
    # This verifies the actual Firebase token
    decoded_token = auth.verify_id_token(id_token)
    uid = decoded_token["uid"]
    
    # Sync user in the backend database
    user_repo.ensure_user(uid, email=decoded_token.get("email"))
    
    return {"uid": uid, "email": decoded_token.get("email"), "decoded_token": decoded_token}

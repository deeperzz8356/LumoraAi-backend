from __future__ import annotations

from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore, storage

from app.core.config import get_settings


import os
import json

@lru_cache
def initialize_firebase_app() -> firebase_admin.App:
    settings = get_settings()
    if firebase_admin._apps:
        return firebase_admin.get_app()
        
    # Option 1: Load from a raw JSON string in the environment variable
    firebase_json_env = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if firebase_json_env:
        try:
            cred_dict = json.loads(firebase_json_env)
            cred = credentials.Certificate(cred_dict)
            return firebase_admin.initialize_app(cred, {"storageBucket": settings.firebase_storage_bucket or None})
        except Exception as e:
            print(f"Error loading FIREBASE_CREDENTIALS_JSON: {e}")

    # Option 2: Load from the file path if it exists
    if settings.firebase_credentials_path and os.path.exists(settings.firebase_credentials_path):
        cred = credentials.Certificate(settings.firebase_credentials_path)
        return firebase_admin.initialize_app(cred, {"storageBucket": settings.firebase_storage_bucket or None})
        
    # Fallback to Application Default Credentials
    return firebase_admin.initialize_app(options={"storageBucket": settings.firebase_storage_bucket or None})


def get_firestore_client():
    initialize_firebase_app()
    return firestore.client()


def get_storage_bucket():
    initialize_firebase_app()
    return storage.bucket()

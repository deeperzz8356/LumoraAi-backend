from __future__ import annotations

from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore, storage

from app.core.config import get_settings


@lru_cache
def initialize_firebase_app() -> firebase_admin.App:
    settings = get_settings()
    if firebase_admin._apps:
        return firebase_admin.get_app()
    if settings.firebase_credentials_path:
        cred = credentials.Certificate(settings.firebase_credentials_path)
        return firebase_admin.initialize_app(cred, {"storageBucket": settings.firebase_storage_bucket or None})
    return firebase_admin.initialize_app(options={"storageBucket": settings.firebase_storage_bucket or None})


def get_firestore_client():
    initialize_firebase_app()
    return firestore.client()


def get_storage_bucket():
    initialize_firebase_app()
    return storage.bucket()

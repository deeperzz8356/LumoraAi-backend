import json
import os
import sqlite3
from typing import Any

import firebase_admin
from fastapi import APIRouter, Depends, Header, HTTPException
from firebase_admin import auth as firebase_auth, credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field

DATABASE_PATH = os.getenv("DATABASE_PATH", "./billing.sqlite3")
PACKAGE_NAME = os.getenv("PLAY_PACKAGE_NAME", "com.deep.lumoraai")

router = APIRouter()


def _catalog() -> dict[str, dict[str, Any]]:
    raw = os.getenv("PLAY_PRODUCT_CATALOG_JSON", "")
    if not raw:
        raise RuntimeError("PLAY_PRODUCT_CATALOG_JSON is required")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("PLAY_PRODUCT_CATALOG_JSON must be an object")
    for product_id, product in value.items():
        if not isinstance(product_id, str) or not isinstance(product, dict):
            raise RuntimeError("PLAY_PRODUCT_CATALOG_JSON contains an invalid product")
        if product.get("kind") not in {"inapp", "subs"}:
            raise RuntimeError(f"Invalid kind for catalog product {product_id}")
        if product["kind"] == "inapp" and (
            not isinstance(product.get("credits"), int) or product["credits"] <= 0
        ):
            raise RuntimeError(f"Invalid credits for catalog product {product_id}")
    return value


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 5000")
    db.execute("PRAGMA journal_mode = WAL")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS balances (
          uid TEXT PRIMARY KEY, credits INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS play_transactions (
          purchase_token TEXT PRIMARY KEY, uid TEXT NOT NULL,
          product_id TEXT NOT NULL, kind TEXT NOT NULL,
          credits INTEGER NOT NULL DEFAULT 0, verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS entitlements (
          uid TEXT NOT NULL, product_id TEXT NOT NULL,
          purchase_token TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          expiry_time TEXT, auto_renewing INTEGER NOT NULL DEFAULT 0,
          verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(uid, product_id)
        );
        """
    )
    # Keep this migration compatible with databases created by the first
    # version of the service.
    columns = {row["name"] for row in db.execute("PRAGMA table_info(entitlements)")}
    if "subscription_state" not in columns:
        db.execute(
           "ALTER TABLE entitlements ADD COLUMN subscription_state TEXT NOT NULL DEFAULT 'UNKNOWN'"
        )
    return db


def _firebase_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer ") or len(authorization) <= 7:
        raise HTTPException(401, "Bearer Firebase ID token required")
    try:
        if not firebase_admin._apps:
            path = os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]
            firebase_admin.initialize_app(credentials.Certificate(path))
        return firebase_auth.verify_id_token(authorization[7:])
    except Exception as exc:
        raise HTTPException(401, "Invalid authentication token") from exc


def _publisher():
    path = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON")
    if not path:
        raise RuntimeError("PLAY_SERVICE_ACCOUNT_JSON is required")
    creds = service_account.Credentials.from_service_account_file(
        path, scopes=["https://www.googleapis.com/auth/androidpublisher"]
    )
    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


class VerifyRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=128)
    purchase_token: str = Field(min_length=1, max_length=4096)


@router.post("/google-play/verify")
def verify_purchase(payload: VerifyRequest, user: dict[str, Any] = Depends(_firebase_user)):
    uid = user["uid"]
    catalog = _catalog()
    product = catalog.get(payload.product_id)
    if not product or product.get("kind") not in {"inapp", "subs"}:
        raise HTTPException(400, "Unknown Play product")

    db = _db()
    try:
        existing = db.execute(
            "SELECT uid, product_id, credits FROM play_transactions WHERE purchase_token = ?",
            (payload.purchase_token,),
        ).fetchone()
        if existing and existing["uid"] != uid:
            raise HTTPException(409, "Purchase token belongs to another account")
        if existing and existing["product_id"] != payload.product_id:
            raise HTTPException(409, "Purchase token does not match this product")
        if existing and product["kind"] == "inapp":
            balance = db.execute("SELECT credits FROM balances WHERE uid = ?", (uid,)).fetchone()
            return {"status": "success", "balance": balance["credits"] if balance else 0, "idempotent": True}

        publisher = _publisher()
        if product["kind"] == "inapp":
            try:
                verified = publisher.purchases().products().get(
                    packageName=PACKAGE_NAME, productId=payload.product_id,
                    token=payload.purchase_token
                ).execute()
            except HttpError as exc:
                if exc.resp.status in {400, 404}:
                    raise HTTPException(409, "Purchase token is invalid") from exc
                raise
            if verified.get("purchaseState") != 0 or verified.get("consumptionState") == 1:
                raise HTTPException(409, "Purchase is not eligible")
            credits = int(product.get("credits", 0))
            if credits <= 0:
                raise HTTPException(500, "Catalog credit value is invalid")
        else:
            try:
                verified = publisher.purchases().subscriptionsv2().get(
                    packageName=PACKAGE_NAME, token=payload.purchase_token
                ).execute()
            except HttpError as exc:
                if exc.resp.status in {400, 404}:
                    raise HTTPException(409, "Subscription token is invalid") from exc
                raise
            subscription_state = verified.get("subscriptionState")
            active = subscription_state in {
                "SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"
            }
            line_items = verified.get("lineItems", [])
            line_item = next((item for item in line_items if item.get("productId") == payload.product_id), None)
            if line_item is None:
                raise HTTPException(409, "Purchase product does not match the requested catalog product")
            expiry_time = line_item.get("expiryTime")
            auto_renewing = bool(line_item.get("autoRenewingPlan", {}).get("autoRenewEnabled", False))
            credits = 0

        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO balances(uid) VALUES (?)", (uid,))
        if not existing:
            db.execute(
                "INSERT INTO play_transactions(purchase_token,uid,product_id,kind,credits) VALUES (?,?,?,?,?)",
                (payload.purchase_token, uid, payload.product_id, product["kind"], credits),
            )
        if credits:
            db.execute("UPDATE balances SET credits = credits + ? WHERE uid = ?", (credits, uid))
        if product["kind"] == "subs":
            db.execute(
                """INSERT OR REPLACE INTO entitlements
                   (uid,product_id,purchase_token,active,expiry_time,auto_renewing,subscription_state)
                   VALUES (?,?,?,?,?,?,?)""",
                (uid, payload.product_id, payload.purchase_token, int(active), expiry_time,
                 int(auto_renewing), subscription_state),
            )
        db.commit()
        balance = db.execute("SELECT credits FROM balances WHERE uid = ?", (uid,)).fetchone()
        return {
            "status": "success" if product["kind"] == "inapp" or active else "inactive",
            "balance": balance["credits"],
            "active": active if product["kind"] == "subs" else True,
            "idempotent": bool(existing),
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, "Google Play verification unavailable") from exc
    finally:
        db.close()


@router.get("/entitlements")
def get_entitlements(user: dict[str, Any] = Depends(_firebase_user)):
    """Return server-owned subscription state; clients never infer entitlement locally."""
    db = _db()
    try:
        rows = db.execute(
            """SELECT product_id, active, expiry_time, auto_renewing, subscription_state
               FROM entitlements WHERE uid = ?""", (user["uid"],)
        ).fetchall()
        return {"entitlements": [dict(row) for row in rows]}
    finally:
        db.close()
import json

import pytest

from app import main


class _Request:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class _Products:
    def __init__(self, value):
        self.value = value

    def get(self, **kwargs):
        return _Request(self.value)


class _Purchases:
    def __init__(self, product=None, subscription=None):
        self._product = product
        self._subscription = subscription

    def products(self):
        return _Products(self._product)

    def subscriptionsv2(self):
        return _Products(self._subscription)


class _Publisher:
    def __init__(self, product=None, subscription=None):
        self._purchases = _Purchases(product, subscription)

    def purchases(self):
        return self._purchases


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "billing.sqlite3"))
    monkeypatch.setenv(
        "PLAY_PRODUCT_CATALOG_JSON",
        json.dumps({"credits_starter": {"kind": "inapp", "credits": 50},
                    "pro_monthly": {"kind": "subs", "entitlement": "pro"}}),
    )


def test_one_time_purchase_is_credited_once(configured, monkeypatch):
    monkeypatch.setattr(
        main, "_publisher",
        lambda: _Publisher(product={"purchaseState": 0, "consumptionState": 0}),
    )
    payload = main.VerifyRequest(product_id="credits_starter", purchase_token="token-1")
    assert main.verify_purchase(payload, {"uid": "user-1"})["balance"] == 50
    result = main.verify_purchase(payload, {"uid": "user-1"})
    assert result["idempotent"] is True
    assert result["balance"] == 50


def test_purchase_token_cannot_move_accounts(configured, monkeypatch):
    monkeypatch.setattr(
        main, "_publisher",
        lambda: _Publisher(product={"purchaseState": 0, "consumptionState": 0}),
    )
    payload = main.VerifyRequest(product_id="credits_starter", purchase_token="token-2")
    main.verify_purchase(payload, {"uid": "owner"})
    with pytest.raises(main.HTTPException) as error:
        main.verify_purchase(payload, {"uid": "attacker"})
    assert error.value.status_code == 409


def test_subscription_retry_refreshes_lifecycle(configured, monkeypatch):
    publisher = _Publisher(
        subscription={
            "subscriptionState": "SUBSCRIPTION_STATE_ACTIVE",
            "lineItems": [{"productId": "pro_monthly", "expiryTime": "2030-01-01T00:00:00Z",
                           "autoRenewingPlan": {"autoRenewEnabled": True}}],
        }
    )
    monkeypatch.setattr(main, "_publisher", lambda: publisher)
    payload = main.VerifyRequest(product_id="pro_monthly", purchase_token="sub-1")
    assert main.verify_purchase(payload, {"uid": "user-1"})["active"] is True

    publisher._purchases._subscription = {
        "subscriptionState": "SUBSCRIPTION_STATE_CANCELED",
        "lineItems": [{"productId": "pro_monthly", "expiryTime": "2025-01-01T00:00:00Z"}],
    }
    result = main.verify_purchase(payload, {"uid": "user-1"})
    assert result["status"] == "inactive"
    assert main.get_entitlements({"uid": "user-1"})["entitlements"][0]["active"] == 0

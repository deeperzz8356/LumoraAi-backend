from app.services.subscription_plans import get_plan_by_code, get_plan_catalog


def test_plan_catalog_contains_expected_subscription_tiers() -> None:
    catalog = get_plan_catalog()
    plan_codes = {plan["code"] for plan in catalog["plans"]}

    # Catalog codes MUST match the real Play/RevenueCat product ids so the
    # RevenueCat webhook mapping and /subscriptions resolve to a real plan
    # (previously the catalog used free/starter/pro while the webhook mapped to
    # pro_monthly/pro_annual/elite_pro, silently granting 0 credits).
    assert "free" in plan_codes
    assert "pro_monthly" in plan_codes
    assert "pro_annual" in plan_codes
    assert "elite_pro" in plan_codes


def test_free_plan_has_seven_trial_credits() -> None:
    plan = get_plan_by_code("free")

    assert plan is not None
    assert plan["signup_bonus_credits"] == 7

from app.services.subscription_plans import get_plan_by_code, get_plan_catalog


def test_plan_catalog_contains_expected_subscription_tiers() -> None:
    catalog = get_plan_catalog()
    plan_codes = {plan["code"] for plan in catalog["plans"]}

    assert "free" in plan_codes
    assert "starter" in plan_codes
    assert "pro" in plan_codes


def test_free_plan_has_one_signup_credit() -> None:
    plan = get_plan_by_code("free")

    assert plan is not None
    assert plan["signup_bonus_credits"] == 1

"""
Regression tests for the RevenueCat product -> plan-code mapping.

Previously billing_service._map_product_to_plan returned pro_monthly/pro_annual/
elite_pro, none of which existed in the plan catalog, so _activate_from_webhook
resolved to an empty plan and granted 0 credits (a paid subscription became a
silent no-op). These tests lock in that every mapped code resolves to a real
catalog plan with positive monthly credits.
"""

from app.services.billing_service import billing_service
from app.services.subscription_plans import get_plan_by_code


def test_every_mapped_product_resolves_to_a_real_plan():
    samples = [
        "pro_monthly",
        "com.deep.lumoraai.pro_monthly",
        "pro_annual",
        "some_annual_sku",
        "elite_pro",
        "elite_tier",
        "monthly",
    ]
    for product_id in samples:
        code = billing_service._map_product_to_plan(product_id)
        plan = get_plan_by_code(code)
        assert plan is not None, f"{product_id!r} mapped to unknown plan {code!r}"
        assert plan["monthly_credits"] > 0, (
            f"{product_id!r} -> {code!r} must grant credits, got "
            f"{plan['monthly_credits']}"
        )


def test_specific_mappings():
    assert billing_service._map_product_to_plan("pro_monthly") == "pro_monthly"
    assert billing_service._map_product_to_plan("pro_annual") == "pro_annual"
    assert billing_service._map_product_to_plan("elite_pro") == "elite_pro"
    # Unknown/free products still resolve to the free plan.
    assert billing_service._map_product_to_plan("something_else") == "free"

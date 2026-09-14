import copy
import pytest
from fastapi import HTTPException
from app.services import tool_policy as policy


@pytest.fixture(autouse=True)
def reset_policy():
    saved = copy.deepcopy(policy._tools)
    policy._tools = {key: {"enabled": True, "credit_cost": cost} for key, cost in policy.DEFAULT_COSTS.items()}
    yield
    policy._tools = saved


def parameter(value):
    return {"defaultValue": {"value": value}}


@pytest.mark.parametrize("tool", policy.DEFAULT_COSTS)
def test_every_tool_can_be_disabled(tool):
    policy.apply_parameters({f"tool_{tool}_enabled": parameter("false")})
    with pytest.raises(HTTPException) as error:
        policy.authorize(tool, policy.snapshot()["revision"])
    assert error.value.status_code == 503


@pytest.mark.parametrize("tool", policy.DEFAULT_COSTS)
def test_each_tool_supports_zero_cost(tool):
    policy.apply_parameters({f"tool_{tool}_credit_cost": parameter("0")})
    assert policy.authorize(tool, policy.snapshot()["revision"]) == 0


@pytest.mark.parametrize("value", ["-1", "1.5", "no", "100001", None, True, 2])
def test_invalid_prices_keep_last_valid_value(value):
    policy.apply_parameters({"tool_logo_credit_cost": parameter("8")})
    policy.apply_parameters({"tool_logo_credit_cost": parameter(value)})
    assert policy.snapshot()["tools"]["logo"]["credit_cost"] == 8


def test_conditions_are_not_used_for_global_prices():
    policy.apply_parameters({"tool_logo_credit_cost": {**parameter("2"), "conditionalValues": {"vip": {"value": "0"}}}})
    assert policy.authorize("logo", None) == 1


def test_price_change_rejects_old_and_legacy_submissions():
    old = policy.snapshot()["revision"]
    policy.apply_parameters({"tool_text_to_image_credit_cost": parameter("9")})
    for revision in (old, None):
        with pytest.raises(HTTPException) as error:
            policy.authorize("text_to_image", revision)
        assert error.value.status_code == 409
    assert policy.authorize("text_to_image", policy.snapshot()["revision"]) == 9


def test_snapshot_cost_does_not_change_for_accepted_job():
    accepted = policy.authorize("text_to_video", policy.snapshot()["revision"])
    policy.apply_parameters({"tool_text_to_video_credit_cost": parameter("19")})
    assert accepted == 5


def test_wrong_tool_for_endpoint_is_rejected():
    with pytest.raises(HTTPException) as error:
        policy.authorize("compress", None, allowed={"text_to_image"})
    assert error.value.status_code == 400


def test_missing_parameters_keep_last_valid_snapshot():
    policy.apply_parameters({"tool_avatar_enabled": parameter("false")})
    before = policy.snapshot()
    assert policy.apply_parameters({}) == before

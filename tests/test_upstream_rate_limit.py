"""
Unit tests for the Bug 1 upstream 429 retry/backoff/concurrency helper
(app/utils/upstream_rate_limit.py).

These are focused unit tests for the new utility introduced by Task 3.3. They
verify: retriable-vs-non-retriable classification, retryDelay parsing, bounded
jittered backoff, honest-failure raising when retries are exhausted, that a
retry can succeed, that non-retriable errors are surfaced without retry, and
that the in-process semaphore bounds concurrency without delaying below-bound
calls.
"""

import asyncio
import random

import pytest

from app.utils import upstream_rate_limit as url


VERTEX_429 = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': "
    "'RESOURCE_EXHAUSTED', 'message': 'Quota exceeded', "
    "'details': [{'retryDelay': '17s'}]}}"
)


def test_is_retriable_detects_429_and_resource_exhausted():
    assert url.is_retriable_rate_limit(VERTEX_429) is True
    assert url.is_retriable_rate_limit(RuntimeError(VERTEX_429)) is True
    assert url.is_retriable_rate_limit({"status": "error", "message": VERTEX_429}) is True
    assert url.is_retriable_rate_limit("500 RESOURCE_EXHAUSTED") is True


def test_is_retriable_rejects_non_retriable_errors():
    for msg in (
        "400 INVALID_ARGUMENT",
        "401 UNAUTHENTICATED",
        "403 PERMISSION_DENIED",
        "took 1429ms",  # must not match a bare 429 substring
        "",
        None,
    ):
        assert url.is_retriable_rate_limit(msg) is False, msg


def test_parse_retry_delay_seconds():
    assert url.parse_retry_delay_seconds(VERTEX_429) == 17.0
    assert url.parse_retry_delay_seconds("429 no hint here") is None


def test_compute_backoff_delay_is_bounded_and_honors_hint():
    rng = random.Random(0)
    # Full jitter keeps delay within [0, capped].
    for attempt in range(6):
        delay = url.compute_backoff_delay(
            attempt, base_seconds=0.5, max_seconds=20.0, rng=rng
        )
        assert 0.0 <= delay <= 20.0
    # retryDelay hint acts as a floor, still capped by max_seconds.
    delay = url.compute_backoff_delay(
        0, base_seconds=0.5, max_seconds=20.0, retry_delay_hint=17.0, rng=rng
    )
    assert delay >= 17.0
    capped = url.compute_backoff_delay(
        0, base_seconds=0.5, max_seconds=5.0, retry_delay_hint=17.0, rng=rng
    )
    assert capped == 5.0


def test_call_with_retry_raises_honest_failure_when_exhausted():
    calls = {"n": 0}

    async def always_429():
        calls["n"] += 1
        return {"status": "error", "message": VERTEX_429}

    async def run():
        return await url.call_with_retry(
            always_429,
            max_retries=3,
            base_seconds=0.5,
            max_seconds=20.0,
            concurrency_limit=2,
            sleep_enabled=False,
        )

    with pytest.raises(url.UpstreamRateLimitError) as exc:
        asyncio.run(run())

    assert exc.value.http_status in (429, 503)
    # 1 initial attempt + 3 retries.
    assert calls["n"] == 4


def test_call_with_retry_succeeds_after_transient_429():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(VERTEX_429)
        return {"status": "success", "video_url": "ok"}

    async def run():
        return await url.call_with_retry(
            flaky,
            max_retries=5,
            base_seconds=0.5,
            max_seconds=20.0,
            concurrency_limit=2,
            sleep_enabled=False,
        )

    result = asyncio.run(run())
    assert result["status"] == "success"
    assert calls["n"] == 3


def test_call_with_retry_surfaces_non_retriable_without_retry():
    calls = {"n": 0}

    async def bad_request():
        calls["n"] += 1
        raise RuntimeError("400 INVALID_ARGUMENT")

    async def run():
        return await url.call_with_retry(
            bad_request,
            max_retries=5,
            base_seconds=0.5,
            max_seconds=20.0,
            concurrency_limit=2,
            sleep_enabled=False,
        )

    with pytest.raises(RuntimeError, match="400 INVALID_ARGUMENT"):
        asyncio.run(run())
    # No retry loop for a non-retriable error.
    assert calls["n"] == 1


def test_semaphore_bounds_concurrency():
    limit = 2
    state = {"active": 0, "peak": 0}

    async def worker():
        async def body():
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            await asyncio.sleep(0.02)
            state["active"] -= 1
            return {"status": "success"}

        return await url.call_with_retry(
            body,
            max_retries=0,
            base_seconds=0.0,
            max_seconds=0.0,
            concurrency_limit=limit,
            sleep_enabled=False,
        )

    async def run():
        await asyncio.gather(*(worker() for _ in range(6)))

    asyncio.run(run())
    assert state["peak"] <= limit

"""
Bug 1 (isBugCondition1) — honest handling of upstream Vertex 429 RESOURCE_EXHAUSTED.

This module centralizes the retry/backoff/concurrency behavior that the
generation services use when calling Vertex AI, so a transient upstream rate
limit is retried (bounded exponential backoff + jitter, honoring Vertex's
``retryDelay`` hint) and — if retries are exhausted — surfaced as an HONEST
failure that the HTTP layer can map to 429/503, never a 200-with-no-output.

Platform constraint (Render FREE plan): all state is in-process only. There is
no Redis, Celery, or external queue. Concurrency is bounded by an in-process
``asyncio.Semaphore`` sized to the plan's safe concurrency.

Design notes:
- A retriable failure is a Vertex ``429`` / ``RESOURCE_EXHAUSTED``. Non-retriable
  errors (400/401/403 and anything else) are re-raised immediately WITHOUT any
  retry/backoff so their existing handling is preserved (preservation req 3.2).
- The provider layer currently *swallows* exceptions into an error dict
  (``{"status": "error", "message": ...}``). We therefore detect a retriable 429
  from BOTH raised exceptions AND returned error dicts.
- Backoff sleeping can be disabled via settings so the test suite runs fast.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

# HTTP status the API layer should return when upstream retries are exhausted.
# 503 (Service Unavailable) communicates "the upstream is overloaded, retry
# later" more accurately than a bare 429 for a server-to-server dependency, and
# both are accepted honest-failure signals by the contract tests.
RETRY_EXHAUSTED_STATUS = 503


class UpstreamRateLimitError(Exception):
    """Raised when a retriable upstream 429 persists after all retry attempts.

    Carries an ``http_status`` (in {429, 503}) so the router can map it to an
    honest HTTP failure response instead of a 200-with-no-output.
    """

    def __init__(
        self,
        message: str,
        *,
        http_status: int = RETRY_EXHAUSTED_STATUS,
        attempts: int = 0,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.attempts = attempts


def is_retriable_rate_limit(error: Any) -> bool:
    """Return True iff ``error`` represents a retriable upstream 429.

    Accepts either an exception, an error string/message, or a provider result
    dict (``{"status": "error", "message": ...}``). Non-429 errors (e.g. 400,
    401, 403) return False so they are surfaced without retry/backoff.
    """
    text = _error_text(error)
    if not text:
        return False
    lowered = text.lower()
    if "resource_exhausted" in lowered:
        return True
    # Match a standalone 429 status token (avoid matching e.g. "1429ms").
    return re.search(r"(^|[^0-9])429([^0-9]|$)", text) is not None


def parse_retry_delay_seconds(error: Any) -> Optional[float]:
    """Extract Vertex's ``retryDelay`` hint (e.g. ``'17s'``) if present."""
    text = _error_text(error)
    if not text:
        return None
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?\s*(\d+(?:\.\d+)?)\s*s", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _error_text(error: Any) -> str:
    if error is None:
        return ""
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        # Provider error dict shape: {"status": "error", "message": ...}
        return str(error.get("message") or error.get("error") or "")
    return str(error)


def compute_backoff_delay(
    attempt: int,
    *,
    base_seconds: float,
    max_seconds: float,
    retry_delay_hint: Optional[float] = None,
    rng: Optional[random.Random] = None,
) -> float:
    """Bounded exponential backoff with full jitter, honoring ``retryDelay``.

    ``attempt`` is 0-based (0 = the delay before the first retry). When Vertex
    supplies a ``retryDelay`` hint we honor it as a floor (never wait less than
    the server asked), still capped by ``max_seconds``.
    """
    rand = rng or random
    exp = base_seconds * (2 ** max(0, attempt))
    capped = min(exp, max_seconds)
    # Full jitter: sleep a random amount in [0, capped].
    delay = rand.uniform(0.0, capped) if capped > 0 else 0.0
    if retry_delay_hint is not None:
        delay = max(delay, min(retry_delay_hint, max_seconds))
    return delay


# ---------------------------------------------------------------------------
# In-process concurrency limiter (no external queue / Render FREE plan).
# ---------------------------------------------------------------------------
_semaphore: Optional[asyncio.Semaphore] = None
_semaphore_limit: Optional[int] = None


def get_upstream_semaphore(limit: int) -> asyncio.Semaphore:
    """Return a process-wide semaphore sized to ``limit`` (created lazily).

    Recreated if the configured limit changes (useful for tests).
    """
    global _semaphore, _semaphore_limit
    if _semaphore is None or _semaphore_limit != limit:
        _semaphore = asyncio.Semaphore(limit)
        _semaphore_limit = limit
    return _semaphore


async def call_with_retry(
    func: Callable[[], Awaitable[Any]],
    *,
    max_retries: int,
    base_seconds: float,
    max_seconds: float,
    concurrency_limit: int,
    sleep_enabled: bool = True,
    sleep: Optional[Callable[[float], Awaitable[None]]] = None,
    rng: Optional[random.Random] = None,
) -> Any:
    """Invoke ``func`` under the concurrency semaphore with 429 retry/backoff.

    ``func`` is an async zero-arg callable returning the provider result. It may
    either raise on a 429 or return a provider error dict describing the 429 —
    both are detected as retriable.

    Behavior:
    - Below the concurrency bound the call proceeds with NO added delay
      (preservation req 3.3).
    - On a retriable 429, retry up to ``max_retries`` times with bounded
      exponential backoff + jitter, honoring any ``retryDelay`` hint.
    - Non-retriable errors are re-raised / returned unchanged immediately
      (preservation req 3.2).
    - If retries are exhausted, raise ``UpstreamRateLimitError`` so the caller
      can surface an honest {429, 503} failure.
    """
    sleeper = sleep or asyncio.sleep
    semaphore = get_upstream_semaphore(concurrency_limit)
    last_rate_limit_text = "upstream rate limited (429 RESOURCE_EXHAUSTED)"

    async with semaphore:
        for attempt in range(max_retries + 1):
            retriable_error: Any = None
            try:
                result = await func()
            except UpstreamRateLimitError:
                raise
            except Exception as exc:  # noqa: BLE001 - classify then re-raise if needed
                if is_retriable_rate_limit(exc):
                    retriable_error = exc
                else:
                    raise
            else:
                # The provider may swallow a 429 into an error dict rather than
                # raising. Treat that as retriable too.
                if is_retriable_rate_limit(result):
                    retriable_error = result
                else:
                    return result

            last_rate_limit_text = _error_text(retriable_error) or last_rate_limit_text

            if attempt >= max_retries:
                break

            delay = compute_backoff_delay(
                attempt,
                base_seconds=base_seconds,
                max_seconds=max_seconds,
                retry_delay_hint=parse_retry_delay_seconds(retriable_error),
                rng=rng,
            )
            logger.warning(
                "Upstream 429 (attempt %d/%d); backing off %.3fs before retry",
                attempt + 1,
                max_retries + 1,
                delay,
            )
            if sleep_enabled and delay > 0:
                await sleeper(delay)

    raise UpstreamRateLimitError(
        f"Upstream rate limit persisted after {max_retries + 1} attempts: "
        f"{last_rate_limit_text}",
        http_status=RETRY_EXHAUSTED_STATUS,
        attempts=max_retries + 1,
    )

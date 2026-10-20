from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

from src.api_client import ApiClient, ApiError

logger = logging.getLogger(__name__)

OnOrderCallback = Callable[[str, Optional[float], Optional[str]], Awaitable[None]]


class OrderProcessor:
    def __init__(
        self,
        client:        ApiClient,
        queue:         asyncio.Queue,
        trader_id:     str,
        chat_id:       int,  # For metrics tracking
        on_taken:      OnOrderCallback,
        on_failed:     OnOrderCallback,
        on_auth_error: Optional[OnOrderCallback] = None,
    ) -> None:
        self._client        = client
        self._queue         = queue
        self._trader_id     = trader_id
        self._chat_id       = chat_id
        self._on_taken      = on_taken
        self._on_failed     = on_failed
        self._on_auth_error = on_auth_error
        self._running       = False

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("Processor started")
        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                # Update queue depth metric
                try:
                    from src import metrics
                    metrics.update_queue_depth(self._chat_id, self._queue.qsize())
                except (ImportError, AttributeError):
                    pass

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                await self._take(item)
            except Exception as exc:
                logger.exception("Unexpected error taking order %s: %s", item.get("slug"), exc)
            finally:
                self._queue.task_done()

    async def _take(self, item: dict) -> None:
        slug:   str             = item["slug"]
        amount: Optional[float] = item["amount"]
        detected_at: Optional[float] = item.get("detected_at")

        logger.info("Taking order %s (amount=%s RUB)", slug, amount)

        start_time = time.time()
        success = False

        try:
            result = await self._client.take_order(slug, self._trader_id)
            logger.info("Order %s → status=%s", slug, result.get("status"))
            success = True

            # Record metrics for successful grab
            try:
                from src import metrics
                grab_duration = time.time() - start_time
                metrics.record_order_taken(self._chat_id)
                metrics.order_grab_duration_seconds.labels(
                    chat_id=str(self._chat_id),
                    result="success"
                ).observe(grab_duration)

                # Record time to grab (from detection to successful grab)
                if detected_at:
                    time_to_grab = time.time() - detected_at
                    metrics.record_time_to_grab(self._chat_id, time_to_grab)
            except (ImportError, AttributeError):
                pass

            await self._on_taken(slug, amount, None)

        except ApiError as exc:
            grab_duration = time.time() - start_time

            # Record metrics for failed grab
            try:
                from src import metrics
                metrics.order_grab_duration_seconds.labels(
                    chat_id=str(self._chat_id),
                    result="failure"
                ).observe(grab_duration)
            except (ImportError, AttributeError):
                pass

            if exc.is_race_condition:
                # Race condition - don't treat as error, just log
                logger.info("Order %s already taken by another trader (HTTP %d)", slug, exc.status)

                try:
                    from src import metrics
                    metrics.record_order_failed(self._chat_id, "race_condition")
                except (ImportError, AttributeError):
                    pass

                await self._on_failed(slug, amount, "race_condition")

            elif exc.is_auth_error:
                logger.error("Auth error taking order %s — check API credentials", slug)

                try:
                    from src import metrics
                    metrics.record_order_failed(self._chat_id, "auth_error")
                except (ImportError, AttributeError):
                    pass

                cb = self._on_auth_error if self._on_auth_error is not None else self._on_failed
                await cb(slug, amount, "auth_error")

            else:
                # Check for specific error messages in response body
                error_reason = "unknown"
                if isinstance(exc.body, dict):
                    error_msg = exc.body.get("error", "")
                    if "not enough balance" in error_msg.lower():
                        error_reason = "insufficient_balance"
                    elif error_msg:
                        error_reason = f"api_error: {error_msg}"

                logger.error("API error taking order %s: %s", slug, exc)

                try:
                    from src import metrics
                    metrics.record_order_failed(self._chat_id, error_reason)
                except (ImportError, AttributeError):
                    pass

                await self._on_failed(slug, amount, error_reason)

        except Exception as exc:
            grab_duration = time.time() - start_time
            logger.error("Error taking order %s: %s", slug, exc)

            try:
                from src import metrics
                metrics.order_grab_duration_seconds.labels(
                    chat_id=str(self._chat_id),
                    result="failure"
                ).observe(grab_duration)
                metrics.record_order_failed(self._chat_id, f"exception: {str(exc)}")
            except (ImportError, AttributeError):
                pass

            await self._on_failed(slug, amount, f"exception: {str(exc)}")

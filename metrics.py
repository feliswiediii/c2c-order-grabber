"""
Prometheus Metrics for C2C Order Grabber Bot

Exposes metrics on http://localhost:9090/metrics for Prometheus scraping.
"""

from __future__ import annotations

import logging
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

# ============================================================================
# COUNTERS (monotonically increasing values)
# ============================================================================

# Orders
orders_seen_total = Counter(
    "orders_seen_total",
    "Total number of new orders detected by monitor",
    ["chat_id"]
)

orders_taken_total = Counter(
    "orders_taken_total",
    "Total number of orders successfully taken",
    ["chat_id"]
)

orders_failed_total = Counter(
    "orders_failed_total",
    "Total number of orders that failed to be taken",
    ["chat_id", "reason"]  # reason: race_condition, auth_error, insufficient_balance, etc.
)

# API Requests
api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests made",
    ["endpoint", "method", "status"]  # status: 2xx, 4xx, 5xx, error
)

# Poll Cycles
poll_cycles_total = Counter(
    "poll_cycles_total",
    "Total number of poll cycles executed",
    ["chat_id", "result"]  # result: success, error
)

# Rate Limiting
rate_limit_hits_total = Counter(
    "rate_limit_hits_total",
    "Total number of HTTP 429 rate limit responses received",
    ["chat_id"]
)

# Auth Events
auth_refresh_total = Counter(
    "auth_refresh_total",
    "Total number of credential refresh attempts",
    ["chat_id", "result"]  # result: success, failure
)

# ============================================================================
# GAUGES (current values that can go up or down)
# ============================================================================

active_sessions = Gauge(
    "active_sessions",
    "Number of active user sessions (monitoring tasks)"
)

queue_depth = Gauge(
    "queue_depth",
    "Number of orders waiting in processing queue",
    ["chat_id"]
)

current_poll_interval_seconds = Gauge(
    "current_poll_interval_seconds",
    "Current adaptive polling interval in seconds",
    ["chat_id"]
)

# ============================================================================
# HISTOGRAMS (distribution of values)
# ============================================================================

# Polling latency
poll_duration_seconds = Histogram(
    "poll_duration_seconds",
    "Duration of poll cycle (API call to get orders)",
    ["chat_id"],
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0)  # 50ms to 10s
)

# Order processing latency
order_grab_duration_seconds = Histogram(
    "order_grab_duration_seconds",
    "Duration of order grab attempt (take_order API call)",
    ["chat_id", "result"],  # result: success, failure
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0)
)

# Time from detection to grab
time_to_grab_seconds = Histogram(
    "time_to_grab_seconds",
    "Time from order detection to successful grab",
    ["chat_id"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)  # 100ms to 1 minute
)

# API request latency
api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "Duration of API requests",
    ["endpoint", "method"],
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0)
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

_metrics_server_started = False


def start_metrics_server(port: int = 9090) -> None:
    """
    Start Prometheus metrics HTTP server.

    Args:
        port: Port to expose metrics on (default: 9090)
    """
    global _metrics_server_started

    if _metrics_server_started:
        logger.warning("Metrics server already started")
        return

    try:
        start_http_server(port)
        _metrics_server_started = True
        logger.info(f"Prometheus metrics server started on port {port}")
        logger.info(f"Metrics available at http://localhost:{port}/metrics")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        raise


def record_order_seen(chat_id: int) -> None:
    """Record that an order was detected"""
    orders_seen_total.labels(chat_id=str(chat_id)).inc()


def record_order_taken(chat_id: int) -> None:
    """Record that an order was successfully taken"""
    orders_taken_total.labels(chat_id=str(chat_id)).inc()


def record_order_failed(chat_id: int, reason: str) -> None:
    """
    Record that an order failed to be taken.

    Args:
        chat_id: User's Telegram chat ID
        reason: Failure reason (race_condition, auth_error, insufficient_balance, etc.)
    """
    orders_failed_total.labels(chat_id=str(chat_id), reason=reason).inc()


def record_api_request(endpoint: str, method: str, status: str) -> None:
    """
    Record an API request.

    Args:
        endpoint: API endpoint (e.g., /v2/dashboard/trader/orders)
        method: HTTP method (GET, POST)
        status: Response status (2xx, 4xx, 5xx, error)
    """
    api_requests_total.labels(endpoint=endpoint, method=method, status=status).inc()


def record_poll_cycle(chat_id: int, result: str) -> None:
    """
    Record a poll cycle completion.

    Args:
        chat_id: User's Telegram chat ID
        result: Cycle result (success, error)
    """
    poll_cycles_total.labels(chat_id=str(chat_id), result=result).inc()


def record_rate_limit(chat_id: int) -> None:
    """Record a rate limit hit (HTTP 429)"""
    rate_limit_hits_total.labels(chat_id=str(chat_id)).inc()


def record_auth_refresh(chat_id: int, result: str) -> None:
    """
    Record a credential refresh attempt.

    Args:
        chat_id: User's Telegram chat ID
        result: Refresh result (success, failure)
    """
    auth_refresh_total.labels(chat_id=str(chat_id), result=result).inc()


def update_active_sessions(count: int) -> None:
    """Update the number of active sessions"""
    active_sessions.set(count)


def update_queue_depth(chat_id: int, depth: int) -> None:
    """Update the queue depth for a user"""
    queue_depth.labels(chat_id=str(chat_id)).set(depth)


def update_poll_interval(chat_id: int, interval: float) -> None:
    """Update the current poll interval for a user"""
    current_poll_interval_seconds.labels(chat_id=str(chat_id)).set(interval)


# Context managers for timing
class poll_duration_timer:
    """Context manager for timing poll cycles"""
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.timer = None

    def __enter__(self):
        self.timer = poll_duration_seconds.labels(chat_id=str(self.chat_id)).time()
        return self.timer.__enter__()

    def __exit__(self, *args):
        return self.timer.__exit__(*args)


class order_grab_timer:
    """Context manager for timing order grab attempts"""
    def __init__(self, chat_id: int, result: str = "success"):
        self.chat_id = chat_id
        self.result = result
        self.timer = None

    def __enter__(self):
        self.timer = order_grab_duration_seconds.labels(
            chat_id=str(self.chat_id),
            result=self.result
        ).time()
        return self.timer.__enter__()

    def __exit__(self, *args):
        return self.timer.__exit__(*args)


class api_request_timer:
    """Context manager for timing API requests"""
    def __init__(self, endpoint: str, method: str):
        self.endpoint = endpoint
        self.method = method
        self.timer = None

    def __enter__(self):
        self.timer = api_request_duration_seconds.labels(
            endpoint=self.endpoint,
            method=self.method
        ).time()
        return self.timer.__enter__()

    def __exit__(self, *args):
        return self.timer.__exit__(*args)


def record_time_to_grab(chat_id: int, duration: float) -> None:
    """
    Record the time from order detection to successful grab.

    Args:
        chat_id: User's Telegram chat ID
        duration: Time in seconds
    """
    time_to_grab_seconds.labels(chat_id=str(chat_id)).observe(duration)

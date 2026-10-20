from __future__ import annotations

import asyncio
import logging
import sys
import time

from aiohttp import web

from app import App


def setup_logging() -> None:
    import os
    import config

    # Check if DEBUG mode is enabled via environment variable
    debug_mode = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
    log_level = logging.DEBUG if debug_mode else logging.INFO

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if config.LOG_FILE:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    if debug_mode:
        logging.info("DEBUG mode enabled - showing detailed logs")


# Global health check state
_last_activity_time: float = time.time()
_app_instance: App | None = None


def update_health_check_activity() -> None:
    """Update last activity timestamp for health check"""
    global _last_activity_time
    _last_activity_time = time.time()


async def health_check(request: web.Request) -> web.Response:
    """
    Health check endpoint for Docker HEALTHCHECK and monitoring.
    Returns 200 if bot is healthy, 503 if stale or unhealthy.
    """
    global _last_activity_time, _app_instance

    # Check if app is running
    if _app_instance is None:
        return web.Response(status=503, text="Bot not initialized")

    # Check if there's been recent activity (within last 120 seconds)
    time_since_activity = time.time() - _last_activity_time
    if time_since_activity > 120:
        return web.Response(
            status=503,
            text=f"Bot stale: no activity for {time_since_activity:.0f}s"
        )

    # Check if any user sessions are active
    active_sessions = len(_app_instance._sessions)

    return web.Response(
        status=200,
        text=f"OK: {active_sessions} active sessions, last activity {time_since_activity:.0f}s ago"
    )


async def start_health_server(port: int = 8080) -> web.AppRunner:
    """Start health check HTTP server"""
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)  # Also respond to root

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logging.info(f"Health check server started on port {port}")
    return runner


async def main() -> None:
    global _app_instance

    setup_logging()

    # Start Prometheus metrics server
    try:
        import metrics
        metrics.start_metrics_server(port=9090)
    except Exception as e:
        logging.warning(f"Failed to start metrics server: {e}")

    # Start health check server
    health_runner = await start_health_server(port=8080)

    try:
        _app_instance = App()

        # Update health check initially
        update_health_check_activity()

        await _app_instance.run()
    except Exception:
        logging.exception("Fatal error — bot crashed")
        raise
    finally:
        await health_runner.cleanup()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

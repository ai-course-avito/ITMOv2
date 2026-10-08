"""Prometheus metrics, served at /metrics.

Names are prefixed `omnixon_`. Labels never hold ids or other unbounded values: HTTP
paths are the route templates (`/api/v1/users/{user_id}`). A labelled series that has
not been touched for METRICS_TTL_DAYS (7) is dropped, so a route nobody calls any more
does not stay on the page forever."""

import time
from typing import Callable, Dict, Tuple

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from prometheus_client.core import GaugeMetricFamily

from .config import METRICS_TTL_DAYS

REGISTRY = CollectorRegistry()


class Expiring:
    """A labelled metric that remembers when each series was last used, so that
    `expire()` can remove the ones nobody touched for `ttl` seconds."""

    def __init__(self, metric, clock: Callable[[], float] = time.monotonic):
        self.metric = metric
        self.clock = clock
        self.touched: Dict[Tuple[str, ...], float] = {}

    def labels(self, *values: str):
        self.touched[tuple(values)] = self.clock()
        return self.metric.labels(*values)

    def expire(self, ttl: float) -> int:
        """Remove the series unused for more than `ttl` seconds; returns how many."""
        if ttl <= 0:
            return 0
        limit = self.clock() - ttl
        stale = [values for values, at in self.touched.items() if at < limit]
        for values in stale:
            del self.touched[values]
            self.metric.remove(*values)
        return len(stale)


EXPIRING = []


def expiring(metric) -> Expiring:
    wrapped = Expiring(metric)
    EXPIRING.append(wrapped)
    return wrapped

HTTP_REQUESTS = expiring(
    Counter(
        "omnixon_http_requests_total",
        "HTTP requests",
        ["method", "path", "status"],
        registry=REGISTRY,
    )
)
HTTP_DURATION = expiring(
    Histogram(
        "omnixon_http_request_duration_seconds",
        "Time to the response (to its first byte for streams)",
        ["method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
        registry=REGISTRY,
    )
)
HTTP_IN_FLIGHT = Gauge(
    "omnixon_http_requests_in_flight", "Requests being handled", registry=REGISTRY
)
ACTIVE_STREAMS = Gauge(
    "omnixon_active_streams", "SSE streams being delivered", registry=REGISTRY
)
UPSTREAM_RETRIES = Counter(
    "omnixon_upstream_retries_total",
    "Retries after a failure of the model provider",
    registry=REGISTRY,
)
MCP_TOOL_ERRORS = expiring(
    Counter(
        "omnixon_mcp_tool_errors_total",
        "MCP tool calls whose error went to the model as the result: refused = the tool said it failed, "
        "failed = the call did not get through in MCP_TOOL_ATTEMPTS attempts",
        ["kind"],
        registry=REGISTRY,
    )
)
TOOL_ERRORS = Counter(
    "omnixon_tool_errors_total",
    "Tool calls that raised: the model got a failed result and the run went on",
    registry=REGISTRY,
)
MCP_SERVERS_DROPPED = Counter(
    "omnixon_mcp_servers_dropped_total",
    "MCP servers left out of a request because they were down",
    registry=REGISTRY,
)
REQUESTS_CANCELLED = Counter(
    "omnixon_requests_cancelled_total",
    "Requests stopped because the client went away",
    registry=REGISTRY,
)
STREAMS_INTERRUPTED = Counter(
    "omnixon_streams_interrupted_total",
    "Streams stopped on request (an interrupt, or a new request of the same user)",
    registry=REGISTRY,
)
MEMORIES_EXTRACTED = Counter(
    "omnixon_memories_extracted_total",
    "Memories created from conversations by auto_memory",
    registry=REGISTRY,
)
MESSAGES_EXPIRED = Counter(
    "omnixon_messages_expired_total",
    "Messages deleted because they were older than MESSAGE_TTL_DAYS",
    registry=REGISTRY,
)


class PoolCollector:
    """Size and use of the database pool, read when the metrics are scraped."""

    def __init__(self):
        self.pool = None

    def collect(self):
        if self.pool is None:
            return
        size = GaugeMetricFamily("omnixon_db_pool_size", "Connections in the pool")
        size.add_metric([], self.pool.get_size())
        idle = GaugeMetricFamily("omnixon_db_pool_idle", "Idle connections in the pool")
        idle.add_metric([], self.pool.get_idle_size())
        maximum = GaugeMetricFamily("omnixon_db_pool_max", "Largest size of the pool")
        maximum.add_metric([], self.pool.get_max_size())
        yield from (size, idle, maximum)


POOL = PoolCollector()
REGISTRY.register(POOL)


def expire_stale(ttl_days: float = METRICS_TTL_DAYS) -> int:
    """Drop the labelled series nothing has touched for `ttl_days`."""
    return sum(metric.expire(ttl_days * 86400) for metric in EXPIRING)


def render() -> tuple:
    """(body, content type) of the metrics page."""
    expire_stale()
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence, TextIO

import logfire
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from .config import APP_NAME, LOG_LEVEL
from .masking import mask_text, mask_value

LEVEL_NAMES = {
    1: "trace",
    5: "debug",
    9: "info",
    10: "notice",
    13: "warn",
    17: "error",
    21: "fatal",
}


def _level_name(level_num: int) -> str:
    return LEVEL_NAMES[max(n for n in LEVEL_NAMES if n <= level_num)]


def _isoformat(unix_nanos: int) -> str:
    moment = datetime.fromtimestamp(unix_nanos / 1e9, tz=timezone.utc)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _nest(extra: Dict[str, Any], attributes: Dict[str, Any]) -> Dict[str, Any]:
    """logfire stores dicts and lists as JSON text; turn them back into JSON values."""
    try:
        schema = json.loads(attributes.get("logfire.json_schema") or "{}")
    except ValueError:
        return extra

    nested = dict(extra)
    for key, value in extra.items():
        kind = schema.get("properties", {}).get(key, {}).get("type")
        if kind in ("object", "array") and isinstance(value, str):
            try:
                nested[key] = json.loads(value)
            except ValueError:
                pass
    return nested


def span_to_record(span: ReadableSpan) -> Optional[Dict[str, Any]]:
    """One JSON-able dict for a logfire log or span; None for "pending" span markers."""
    attributes = dict(span.attributes or {})
    span_type = attributes.get("logfire.span_type")
    if span_type == "pending_span":
        return None

    record: Dict[str, Any] = {
        "timestamp": _isoformat(span.start_time),
        "level": _level_name(int(attributes.get("logfire.level_num", 9))),
        "message": mask_text(str(attributes.get("logfire.msg") or span.name)),
        "trace_id": format(span.context.trace_id, "032x"),
        "span_id": format(span.context.span_id, "016x"),
    }
    if span_type == "span":
        record["duration_ms"] = round((span.end_time - span.start_time) / 1e6, 3)

    # what the caller passed; logfire's own bookkeeping and the code location are
    # not part of it
    extra = {
        key: value
        for key, value in attributes.items()
        if not key.startswith(("logfire.", "code.")) and key != "color_message"
    }
    if "code.filepath" in attributes:
        record["source"] = (
            f"{attributes['code.filepath']}:{attributes.get('code.lineno', 0)}"
        )
    if extra:
        record["attributes"] = mask_value(_nest(extra, attributes))

    for event in span.events:
        if event.name == "exception":
            record["exception"] = {
                key: mask_text(str(event.attributes[f"exception.{key}"]))
                for key in ("type", "message", "stacktrace")
                if f"exception.{key}" in event.attributes
            }
    return record


class JsonLinesExporter(SpanExporter):
    """Writes every logfire log (and finished span) as one JSON object per line."""

    def __init__(self, stream: Optional[TextIO] = None) -> None:
        self._stream = stream

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        stream = self._stream or sys.stdout
        for span in spans:
            record = span_to_record(span)
            if record is not None:
                stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        stream.flush()
        return SpanExportResult.SUCCESS


def setup_logging() -> None:
    """Send logfire logs and standard `logging` records to stdout as JSON lines.

    Logs go to the logfire service as well when LOGFIRE_TOKEN is set. LOG_LEVEL
    (default "info") is the lowest level written; "debug" also logs the arguments
    and results of every route and database call, so do not use it in production.
    """
    logfire.configure(
        service_name=APP_NAME or "omnixon",
        send_to_logfire="if-token-present",
        console=False,
        metrics=False,
        distributed_tracing=False,
        inspect_arguments=False,
        min_level=LOG_LEVEL,
        additional_span_processors=[SimpleSpanProcessor(JsonLinesExporter())],
    )

    # Standard logging (uvicorn, libraries) goes the same way. uvicorn installs its
    # own handlers, so replace them.
    handler = logfire.LogfireLoggingHandler()
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(LOG_LEVEL.upper())

    for name in ("fastapi", "uvicorn", "uvicorn.access", "uvicorn.error"):
        quiet = logging.getLogger(name)
        quiet.handlers = []  # their records propagate to the root handler
        quiet.propagate = True
        quiet.setLevel(logging.WARNING)

    logfire.info("Logging is configured", log_level=LOG_LEVEL)

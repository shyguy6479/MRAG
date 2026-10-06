import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Messages are event names, never arbitrary provider exception bodies.
        return json.dumps(
            {
                "level": record.levelname,
                "event": record.getMessage(),
                "logger": record.name,
                "request_id": request_id_var.get(),
                "exception_type": getattr(record, "exception_type", None),
            }
        )


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("atlasrag")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False


class Telemetry:
    def __init__(self, endpoint: str | None = None) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "rag_requests_total", "HTTP requests", ["route", "status"], registry=self.registry
        )
        self.latency = Histogram(
            "rag_request_latency_seconds", "Request latency", ["route"], registry=self.registry
        )
        self.stages = Histogram(
            "rag_stage_latency_seconds", "Stage latency", ["stage"], registry=self.registry
        )
        self.candidates = Counter(
            "retrieval_candidates_total", "Candidates considered", registry=self.registry
        )
        self.tools = Counter(
            "tool_calls_total", "Tool invocations", ["tool"], registry=self.registry
        )
        self.verification_failures = Counter(
            "verification_failures_total", "Failed claims", registry=self.registry
        )
        self.cache = Counter(
            "cache_requests_total", "Cache requests", ["result"], registry=self.registry
        )
        self.cache_ratio = Gauge(
            "cache_hit_ratio", "Process cache hit ratio", registry=self.registry
        )
        self.cache_saved = Counter(
            "cache_latency_saved_seconds", "Estimated latency saved", registry=self.registry
        )
        self.provider = TracerProvider(resource=Resource.create({"service.name": "atlasrag"}))
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            self.provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            )
        self.tracer = self.provider.get_tracer("atlasrag")

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = perf_counter()
        with self.tracer.start_as_current_span(name):
            try:
                yield
            finally:
                self.stages.labels(stage=name).observe(perf_counter() - started)

    def trace_id(self) -> str:
        return format(trace.get_current_span().get_span_context().trace_id, "032x")

    def close(self) -> None:
        self.provider.shutdown()

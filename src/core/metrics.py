from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import set_meter_provider
from opentelemetry import metrics
from src.core.config import settings
import time
import socket

_initialized = False
_meters = {}

def init_metrics():
    global _initialized
    if _initialized:
        return
    if not getattr(settings, "ENABLE_METRICS", True):
        _initialized = True
        return
    reachable = False
    try:
        with socket.create_connection(("localhost", 4317), timeout=0.3) as _:
            reachable = True
    except Exception:
        reachable = False
    try:
        if reachable:
            exporter = OTLPMetricExporter()
            reader = PeriodicExportingMetricReader(exporter)
            provider = MeterProvider(metric_readers=[reader])
        else:
            provider = MeterProvider()
        set_meter_provider(provider)
    except Exception:
        provider = MeterProvider()
        set_meter_provider(provider)
    _initialized = True

def get_meter(name: str):
    if name in _meters:
        return _meters[name]
    m = metrics.get_meter(name)
    _meters[name] = m
    return m

class QueryMetrics:
    def __init__(self):
        init_metrics()
        meter = get_meter("query")
        self.exec_counter = meter.create_counter("sql_exec_count")
        self.rows_hist = meter.create_histogram("sql_rows_hist")
        self.duration_hist = meter.create_histogram("sql_duration_ms")
    def record(self, project_id: int, rows: int, duration_ms: float):
        attrs = {"project_id": str(project_id or "")}
        self.exec_counter.add(1, attrs)
        self.rows_hist.record(rows, attrs)
        self.duration_hist.record(duration_ms, attrs)

import os
from typing import Optional

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.pika import PikaInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy import Engine


def setup_telemetry(service_name: str) -> TracerProvider:
    """
    initialize OpenTelemetry
    :param service_name:
    :return: TracerProvider:
    """

    # 1. 定義資源
    resource = Resource.create(
        attributes={
            "service.name": service_name,
            "service.version": "1.0.0",
        }
    )

    # 2. 設定 Trace Provider
    provider = TracerProvider(resource=resource)

    # 3. 設定Exporter (send to Jaeger)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    # exporter = ConsoleSpanExporter()

    # 4. 加入 Processor (Enhancing batch process performance)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # 設定全域 Provider
    trace.set_tracer_provider(provider)
    return provider


def instrument_app(app: Optional[FastAPI], engine: Optional[Engine] = None) -> None:
    """
    Auto-Instrument OpenTelemetry app
    :param app:
    :param engine:
    :return:
    """

    # 1. FastAPI
    if app:
        FastAPIInstrumentor.instrument_app(app)

    # 2. SQLAlchemy (DB)
    if engine:
        SQLAlchemyInstrumentor().instrument(engine=engine)

    # 3. pika (RabbitMQ)
    PikaInstrumentor().instrument()

    # 4. redis
    RedisInstrumentor().instrument()

    # 5. HTTPX
    HTTPXClientInstrumentor().instrument()

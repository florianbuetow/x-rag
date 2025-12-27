"""Type stubs for opentelemetry.instrumentation.grpc module."""

from opentelemetry.instrumentation.grpc._client import (
    GrpcAioInstrumentorClient as GrpcAioInstrumentorClient,
    GrpcInstrumentorClient as GrpcInstrumentorClient,
)
from opentelemetry.instrumentation.grpc._server import (
    GrpcAioInstrumentorServer as GrpcAioInstrumentorServer,
)

__all__ = [
    "GrpcAioInstrumentorClient",
    "GrpcInstrumentorClient",
    "GrpcAioInstrumentorServer",
]

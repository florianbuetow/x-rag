"""Type stubs for aiokafka module."""

from collections.abc import AsyncIterator
from typing import Any

class ConsumerRecord:
    """Kafka consumer record."""

    topic: str
    partition: int
    offset: int
    key: bytes | None
    value: Any  # Deserialized value
    headers: list[tuple[str, bytes]] | None
    timestamp: int
    timestamp_type: int

class AIOKafkaClient:
    """Internal Kafka client (private API)."""

    async def fetch_all_metadata(self) -> dict[str, Any]: ...

class AIOKafkaProducer:
    """Async Kafka producer client."""

    def __init__(
        self,
        *,
        bootstrap_servers: str | list[str],
        client_id: str | None = None,
        value_serializer: Any | None = None,
        key_serializer: Any | None = None,
        **kwargs: Any,
    ) -> None: ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    async def send_and_wait(
        self,
        topic: str,
        value: object | None = None,
        key: object | None = None,
        partition: int | None = None,
        timestamp_ms: int | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> Any: ...

class AIOKafkaConsumer:
    """Async Kafka consumer client."""

    _client: AIOKafkaClient  # Internal client for health checks

    def __init__(
        self,
        *topics: str,
        bootstrap_servers: str | list[str],
        group_id: str | None = None,
        auto_offset_reset: str | None = None,
        **kwargs: Any,
    ) -> None: ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    def __aiter__(self) -> AsyncIterator[ConsumerRecord]: ...
    async def __anext__(self) -> ConsumerRecord: ...

    async def getmany(
        self,
        timeout_ms: int | None = None,
        max_records: int | None = None,
    ) -> dict[object, list[object]]: ...

    def assignment(self) -> set[object]: ...

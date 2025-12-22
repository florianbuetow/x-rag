"""Thin wrapper for Kafka producer with trace context propagation."""

import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from aiokafka.errors import KafkaError  # type: ignore[import-untyped]
from opentelemetry.propagate import inject

logger = logging.getLogger(__name__)


class KafkaClient:
    """Thin wrapper around Kafka producer with lifecycle management."""

    def __init__(self, bootstrap_servers: str, acks: str | int) -> None:
        """Initialize Kafka client (not started yet).

        Args:
            bootstrap_servers: Kafka bootstrap servers
            acks: Acknowledgment mode ("0", "1", "all", or integer 0, 1, -1)
        """
        self.bootstrap_servers = bootstrap_servers
        # Convert string acks to int for aiokafka
        if isinstance(acks, str):
            if acks == "all":
                self.acks = -1
            else:
                self.acks = int(acks)
        else:
            self.acks = acks
        self.producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Start Kafka producer.

        Raises:
            KafkaError: If producer fails to start
        """
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                acks=self.acks,
                compression_type="gzip",
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self.producer.start()
            logger.info(f"Kafka producer started: {self.bootstrap_servers}")
        except KafkaError as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            raise

    async def stop(self) -> None:
        """Stop Kafka producer gracefully."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish message to Kafka topic with trace context propagation.

        Injects W3C Trace Context headers into Kafka message headers,
        enabling distributed tracing across the async message boundary.

        Args:
            topic: Kafka topic name
            message: Message dict (will be JSON serialized)

        Raises:
            RuntimeError: If producer not started
            KafkaError: If publish fails
        """
        if not self.producer:
            raise RuntimeError("Kafka producer not started")

        try:
            # Inject trace context into headers for propagation to consumer
            headers: dict[str, str] = {}
            inject(headers)

            # Convert headers to Kafka format (list of tuples with bytes values)
            kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

            await self.producer.send_and_wait(
                topic,
                value=message,
                headers=kafka_headers,
            )
            event_type = message["event_type"] if "event_type" in message else "unknown"
            logger.debug(f"Published to {topic}: {event_type}")
        except KafkaError as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Kafka connectivity.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple check: producer is started and ready
            return self.producer is not None
        except Exception as e:
            logger.debug(f"Kafka health check failed: {e}")
            return False

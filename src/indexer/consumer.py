"""Kafka consumer for document change events."""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)


class DocumentEventConsumer:
    """Kafka consumer for document change events.

    Consumes events from the document-changes topic and yields them
    for processing by the indexer.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        auto_offset_reset: str = "earliest",
    ) -> None:
        """Initialize the consumer.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            topic: Kafka topic to consume from
            group_id: Consumer group ID
            auto_offset_reset: Auto offset reset policy (earliest/latest)
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        """Start the Kafka consumer."""
        logger.info(f"Starting Kafka consumer: {self.bootstrap_servers}, topic={self.topic}, group={self.group_id}")

        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

        try:
            await self.consumer.start()
            self._running = True
            logger.info("✓ Kafka consumer started")
        except KafkaError as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Kafka consumer."""
        if self.consumer and self._running:
            logger.info("Stopping Kafka consumer...")
            self._running = False
            await self.consumer.stop()
            logger.info("✓ Kafka consumer stopped")

    async def consume(self) -> AsyncIterator[Dict[str, Any]]:
        """Consume events from Kafka.

        Yields:
            Event dictionaries from Kafka

        Raises:
            RuntimeError: If consumer is not started
        """
        if not self.consumer or not self._running:
            raise RuntimeError("Consumer not started. Call start() first.")

        logger.info(f"Consuming events from topic: {self.topic}")

        try:
            async for message in self.consumer:
                logger.debug(f"Received message: partition={message.partition}, offset={message.offset}")

                event = message.value
                logger.info(f"Event: type={event.get('event_type')}, doc_id={event.get('document_id')}")

                yield event

        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error consuming messages: {e}", exc_info=True)
            raise

    async def health_check(self) -> bool:
        """Check if consumer is healthy.

        Returns:
            True if consumer is running and connected
        """
        if not self.consumer or not self._running:
            return False

        try:
            # Try to get cluster metadata
            await self.consumer._client.fetch_all_metadata()
            return True
        except Exception as e:
            logger.warning(f"Kafka health check failed: {e}")
            return False

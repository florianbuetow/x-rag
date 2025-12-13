"""Tests for Indexer Kafka consumer."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.indexer.consumer import DocumentEventConsumer


class TestDocumentEventConsumerInit:
    """Tests for DocumentEventConsumer initialization."""

    def test_initialization_with_config(self):
        """Consumer initializes with bootstrap servers, topic, and group_id."""
        consumer = DocumentEventConsumer(
            bootstrap_servers="localhost:9092",
            topic="document-changes",
            group_id="test-group",
            auto_offset_reset="earliest",
        )

        assert consumer.bootstrap_servers == "localhost:9092"
        assert consumer.topic == "document-changes"
        assert consumer.group_id == "test-group"
        assert consumer.auto_offset_reset == "earliest"

    def test_initialization_with_custom_offset_reset(self):
        """Consumer accepts custom auto_offset_reset."""
        consumer = DocumentEventConsumer(
            bootstrap_servers="localhost:9092",
            topic="test",
            group_id="group",
            auto_offset_reset="latest",
        )

        assert consumer.auto_offset_reset == "latest"

    def test_initialization_not_running(self):
        """Consumer starts in not-running state."""
        consumer = DocumentEventConsumer(
            bootstrap_servers="localhost:9092",
            topic="test",
            group_id="group",
            auto_offset_reset="earliest",
        )

        assert consumer._running is False
        assert consumer.consumer is None


class TestConsumerLifecycle:
    """Tests for consumer start/stop lifecycle."""

    @pytest.fixture
    def consumer(self):
        """Create a DocumentEventConsumer for testing."""
        return DocumentEventConsumer(
            bootstrap_servers="localhost:9092",
            topic="document-changes",
            group_id="test-group",
            auto_offset_reset="earliest",
        )

    @pytest.mark.asyncio
    async def test_start_creates_consumer(self, consumer):
        """start() creates AIOKafkaConsumer with correct params."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_kafka.return_value = mock_instance

            await consumer.start()

            mock_kafka.assert_called_once()
            call_args = mock_kafka.call_args
            assert call_args[0][0] == "document-changes"  # Topic
            assert call_args[1]["bootstrap_servers"] == "localhost:9092"
            assert call_args[1]["group_id"] == "test-group"
            assert call_args[1]["auto_offset_reset"] == "earliest"

    @pytest.mark.asyncio
    async def test_start_calls_consumer_start(self, consumer):
        """start() calls internal consumer.start()."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_kafka.return_value = mock_instance

            await consumer.start()

            mock_instance.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, consumer):
        """start() sets _running to True."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_kafka.return_value = mock_instance

            await consumer.start()

            assert consumer._running is True

    @pytest.mark.asyncio
    async def test_start_kafka_error_raises(self, consumer):
        """KafkaError during start is logged and re-raised."""
        from aiokafka.errors import KafkaError

        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_instance.start.side_effect = KafkaError("Connection refused")
            mock_kafka.return_value = mock_instance

            with pytest.raises(KafkaError):
                await consumer.start()

            assert consumer._running is False

    @pytest.mark.asyncio
    async def test_stop_calls_consumer_stop(self, consumer):
        """stop() calls internal consumer.stop()."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_kafka.return_value = mock_instance

            await consumer.start()
            await consumer.stop()

            mock_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, consumer):
        """stop() sets _running to False."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_kafka.return_value = mock_instance

            await consumer.start()
            assert consumer._running is True

            await consumer.stop()
            assert consumer._running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self, consumer):
        """stop() when not started is safe (no-op)."""
        # Should not raise
        await consumer.stop()

        # Still not running
        assert consumer._running is False


class TestConsumerConsume:
    """Tests for consuming events."""

    @pytest.fixture
    def consumer(self):
        """Create a DocumentEventConsumer for testing."""
        return DocumentEventConsumer(
            bootstrap_servers="localhost:9092",
            topic="document-changes",
            group_id="test-group",
            auto_offset_reset="earliest",
        )

    @pytest.mark.asyncio
    async def test_consume_before_start_raises(self, consumer):
        """consume() before start() raises RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            async for _ in consumer.consume():
                pass

        assert "Consumer not started" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_consume_yields_events(self, consumer):
        """consume() yields event dictionaries from messages."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            # Create mock messages
            mock_messages = [
                Mock(
                    value={"event_type": "created", "document_id": "doc1"},
                    partition=0,
                    offset=0,
                ),
                Mock(
                    value={"event_type": "updated", "document_id": "doc2"},
                    partition=0,
                    offset=1,
                ),
            ]

            # Create async iterator for messages
            async def async_iter():
                for msg in mock_messages:
                    yield msg

            mock_instance = AsyncMock()
            mock_instance.__aiter__ = lambda self: async_iter()
            mock_kafka.return_value = mock_instance

            await consumer.start()

            events = []
            async for event in consumer.consume():
                events.append(event)
                if len(events) >= 2:
                    break

            assert len(events) == 2
            assert events[0]["event_type"] == "created"
            assert events[0]["document_id"] == "doc1"
            assert events[1]["event_type"] == "updated"
            assert events[1]["document_id"] == "doc2"

    @pytest.mark.asyncio
    async def test_consume_cancelled_error_reraises(self, consumer):
        """CancelledError during consume is re-raised (graceful shutdown)."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            # Create async iterator that raises CancelledError
            async def async_iter_cancelled():
                raise asyncio.CancelledError()
                yield  # Never reached

            mock_instance = AsyncMock()
            mock_instance.__aiter__ = lambda self: async_iter_cancelled()
            mock_kafka.return_value = mock_instance

            await consumer.start()

            with pytest.raises(asyncio.CancelledError):
                async for _ in consumer.consume():
                    pass

    @pytest.mark.asyncio
    async def test_consume_generic_error_reraises(self, consumer):
        """Generic exception during consume is logged and re-raised."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            # Create async iterator that raises error
            async def async_iter_error():
                raise RuntimeError("Kafka error")
                yield  # Never reached

            mock_instance = AsyncMock()
            mock_instance.__aiter__ = lambda self: async_iter_error()
            mock_kafka.return_value = mock_instance

            await consumer.start()

            with pytest.raises(RuntimeError) as exc_info:
                async for _ in consumer.consume():
                    pass

            assert "Kafka error" in str(exc_info.value)


class TestConsumerHealthCheck:
    """Tests for consumer health check."""

    @pytest.fixture
    def consumer(self):
        """Create a DocumentEventConsumer for testing."""
        return DocumentEventConsumer(
            bootstrap_servers="localhost:9092",
            topic="document-changes",
            group_id="test-group",
            auto_offset_reset="earliest",
        )

    @pytest.mark.asyncio
    async def test_health_check_not_running_returns_false(self, consumer):
        """health_check() returns False when not running."""
        result = await consumer.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_running_returns_true(self, consumer):
        """health_check() returns True when running."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_instance._client = AsyncMock()
            mock_instance._client.fetch_all_metadata = AsyncMock()
            mock_kafka.return_value = mock_instance

            await consumer.start()

            result = await consumer.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_metadata_fetch_success(self, consumer):
        """health_check() fetches metadata to verify connection."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_instance._client = AsyncMock()
            mock_instance._client.fetch_all_metadata = AsyncMock()
            mock_kafka.return_value = mock_instance

            await consumer.start()
            await consumer.health_check()

            mock_instance._client.fetch_all_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_metadata_fetch_error(self, consumer):
        """health_check() returns False on metadata fetch error."""
        with patch("src.indexer.consumer.AIOKafkaConsumer") as mock_kafka:
            mock_instance = AsyncMock()
            mock_instance._client = AsyncMock()
            mock_instance._client.fetch_all_metadata = AsyncMock(side_effect=RuntimeError("Connection lost"))
            mock_kafka.return_value = mock_instance

            await consumer.start()

            result = await consumer.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_no_consumer_returns_false(self, consumer):
        """health_check() returns False when consumer is None."""
        consumer.consumer = None
        consumer._running = True  # Edge case

        result = await consumer.health_check()

        assert result is False

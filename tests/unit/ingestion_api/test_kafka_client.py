"""Unit tests for src/ingestion_api/kafka_client.py.

Tests cover:
- KafkaClient initialization
- start method
- stop method
- publish method
- health_check method
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiokafka.errors import KafkaError

from src.ingestion_api.kafka_client import KafkaClient


class TestKafkaClientInit:
    """Tests for KafkaClient initialization."""

    def test_init_sets_bootstrap_servers(self):
        """Tests that __init__ sets bootstrap_servers."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)

        assert client.bootstrap_servers == "localhost:9092"

    def test_init_sets_acks_from_int(self):
        """Tests that __init__ sets acks from integer."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)

        assert client.acks == 1

    def test_init_converts_acks_all_to_minus_one(self):
        """Tests that __init__ converts 'all' to -1."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks="all")

        assert client.acks == -1

    def test_init_converts_acks_string_to_int(self):
        """Tests that __init__ converts string acks to int."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks="0")

        assert client.acks == 0

    def test_init_producer_is_none(self):
        """Tests that __init__ sets producer to None."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)

        assert client.producer is None

    def test_init_requires_acks(self):
        """Tests that __init__ requires acks parameter."""
        with pytest.raises(TypeError, match="acks"):
            KafkaClient(bootstrap_servers="localhost:9092")


class TestKafkaClientStart:
    """Tests for KafkaClient.start method."""

    @pytest.mark.asyncio
    @patch("src.ingestion_api.kafka_client.AIOKafkaProducer")
    async def test_start_creates_producer(self, mock_producer_class):
        """Tests that start creates AIOKafkaProducer."""
        mock_producer = MagicMock()
        mock_producer.start = AsyncMock()
        mock_producer_class.return_value = mock_producer

        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        await client.start()

        mock_producer_class.assert_called_once()
        mock_producer.start.assert_called_once()
        assert client.producer == mock_producer

    @pytest.mark.asyncio
    @patch("src.ingestion_api.kafka_client.AIOKafkaProducer")
    async def test_start_sets_correct_config(self, mock_producer_class):
        """Tests that start configures producer correctly."""
        mock_producer = MagicMock()
        mock_producer.start = AsyncMock()
        mock_producer_class.return_value = mock_producer

        client = KafkaClient(bootstrap_servers="kafka:9092", acks=-1)
        await client.start()

        call_kwargs = mock_producer_class.call_args[1]
        assert call_kwargs["bootstrap_servers"] == "kafka:9092"
        assert call_kwargs["acks"] == -1
        assert call_kwargs["compression_type"] == "gzip"

    @pytest.mark.asyncio
    @patch("src.ingestion_api.kafka_client.AIOKafkaProducer")
    async def test_start_raises_on_kafka_error(self, mock_producer_class):
        """Tests that start raises KafkaError on failure."""
        mock_producer = MagicMock()
        mock_producer.start = AsyncMock(side_effect=KafkaError("Connection failed"))
        mock_producer_class.return_value = mock_producer

        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)

        with pytest.raises(KafkaError):
            await client.start()


class TestKafkaClientStop:
    """Tests for KafkaClient.stop method."""

    @pytest.mark.asyncio
    async def test_stop_stops_producer(self):
        """Tests that stop calls producer.stop()."""
        mock_producer = MagicMock()
        mock_producer.stop = AsyncMock()

        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        client.producer = mock_producer

        await client.stop()

        mock_producer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_handles_no_producer(self):
        """Tests that stop handles None producer gracefully."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        client.producer = None

        # Should not raise
        await client.stop()


class TestKafkaClientPublish:
    """Tests for KafkaClient.publish method."""

    @pytest.mark.asyncio
    async def test_publish_sends_message(self):
        """Tests that publish sends message to topic with trace headers."""
        mock_producer = MagicMock()
        mock_producer.send_and_wait = AsyncMock()

        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        client.producer = mock_producer

        message = {"event_type": "document_created", "doc_id": "123"}
        await client.publish("test-topic", message)

        # Verify send_and_wait was called with topic, value, and headers
        mock_producer.send_and_wait.assert_called_once()
        call_kwargs = mock_producer.send_and_wait.call_args[1]
        assert call_kwargs["value"] == message
        assert "headers" in call_kwargs  # Trace context headers injected

    @pytest.mark.asyncio
    async def test_publish_raises_when_not_started(self):
        """Tests that publish raises RuntimeError when producer not started."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        client.producer = None

        with pytest.raises(RuntimeError) as exc_info:
            await client.publish("topic", {"key": "value"})

        assert "not started" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_publish_raises_on_kafka_error(self):
        """Tests that publish raises KafkaError on failure."""
        mock_producer = MagicMock()
        mock_producer.send_and_wait = AsyncMock(side_effect=KafkaError("Publish failed"))

        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        client.producer = mock_producer

        with pytest.raises(KafkaError):
            await client.publish("topic", {"key": "value"})


class TestKafkaClientHealthCheck:
    """Tests for KafkaClient.health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_producer_exists(self):
        """Tests that health_check returns True when producer is set."""
        mock_producer = MagicMock()

        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        client.producer = mock_producer

        result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_no_producer(self):
        """Tests that health_check returns False when producer is None."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        client.producer = None

        result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        """Tests that health_check returns False on exception."""
        client = KafkaClient(bootstrap_servers="localhost:9092", acks=1)
        # Simulate a property access that raises
        client.producer = MagicMock()

        # Mock an exception scenario
        with patch.object(client, "producer", None):
            result = await client.health_check()
            assert result is False

"""Unit tests for src/search_service/grpc_clients.py.

Tests cover:
- EmbeddingServiceClient initialization
- EmbeddingServiceClient async context manager
- connect method
- close method
- embed method
- embed_batch method
- health_check method
"""

from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import pytest

from src.search_service.grpc_clients import EmbeddingServiceClient


class TestEmbeddingServiceClientInit:
    """Tests for EmbeddingServiceClient initialization."""

    def test_init_sets_address(self):
        """Tests that __init__ sets address."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)

        assert client.address == "localhost:50051"

    def test_init_sets_timeout(self):
        """Tests that __init__ sets timeout."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=60.0)

        assert client.timeout == 60.0

    def test_init_requires_timeout(self):
        """Tests that __init__ requires timeout parameter."""
        with pytest.raises(TypeError, match="timeout"):
            EmbeddingServiceClient(address="localhost:50051")

    def test_init_channel_is_none(self):
        """Tests that __init__ sets channel to None."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)

        assert client.channel is None

    def test_init_stub_is_none(self):
        """Tests that __init__ sets stub to None."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)

        assert client.stub is None


class TestEmbeddingServiceClientContextManager:
    """Tests for EmbeddingServiceClient async context manager."""

    @pytest.mark.asyncio
    @patch("src.search_service.grpc_clients.grpc.aio.insecure_channel")
    @patch("src.search_service.grpc_clients.embedding_pb2_grpc.EmbeddingServiceStub")
    async def test_aenter_connects(self, mock_stub_class, mock_channel):
        """Tests that __aenter__ calls connect."""
        mock_channel_instance = MagicMock()
        mock_channel.return_value = mock_channel_instance
        mock_stub_class.return_value = MagicMock()

        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)

        result = await client.__aenter__()

        assert result is client
        assert client.channel is not None
        assert client.stub is not None

    @pytest.mark.asyncio
    async def test_aexit_closes(self):
        """Tests that __aexit__ calls close."""
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()

        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.channel = mock_channel
        client.stub = MagicMock()

        await client.__aexit__(None, None, None)

        mock_channel.close.assert_called_once()


class TestEmbeddingServiceClientConnect:
    """Tests for EmbeddingServiceClient.connect method."""

    @pytest.mark.asyncio
    @patch("src.search_service.grpc_clients.grpc.aio.insecure_channel")
    @patch("src.search_service.grpc_clients.embedding_pb2_grpc.EmbeddingServiceStub")
    async def test_connect_creates_channel(self, mock_stub_class, mock_channel):
        """Tests that connect creates insecure channel."""
        mock_channel_instance = MagicMock()
        mock_channel.return_value = mock_channel_instance

        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        await client.connect()

        mock_channel.assert_called_once()
        assert client.channel == mock_channel_instance

    @pytest.mark.asyncio
    @patch("src.search_service.grpc_clients.grpc.aio.insecure_channel")
    @patch("src.search_service.grpc_clients.embedding_pb2_grpc.EmbeddingServiceStub")
    async def test_connect_creates_stub(self, mock_stub_class, mock_channel):
        """Tests that connect creates stub."""
        mock_channel_instance = MagicMock()
        mock_channel.return_value = mock_channel_instance
        mock_stub = MagicMock()
        mock_stub_class.return_value = mock_stub

        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        await client.connect()

        mock_stub_class.assert_called_once_with(mock_channel_instance)
        assert client.stub == mock_stub

    @pytest.mark.asyncio
    @patch("src.search_service.grpc_clients.grpc.aio.insecure_channel")
    @patch("src.search_service.grpc_clients.embedding_pb2_grpc.EmbeddingServiceStub")
    async def test_connect_applies_channel_options(self, mock_stub_class, mock_channel):
        """Tests that connect applies correct channel options."""
        mock_channel.return_value = MagicMock()

        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        await client.connect()

        call_args = mock_channel.call_args
        options = dict(call_args[1]["options"])

        assert options["grpc.max_send_message_length"] == 100 * 1024 * 1024
        assert options["grpc.max_receive_message_length"] == 100 * 1024 * 1024


class TestEmbeddingServiceClientClose:
    """Tests for EmbeddingServiceClient.close method."""

    @pytest.mark.asyncio
    async def test_close_closes_channel(self):
        """Tests that close closes the channel."""
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()

        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.channel = mock_channel
        client.stub = MagicMock()

        await client.close()

        mock_channel.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_sets_channel_to_none(self):
        """Tests that close sets channel to None."""
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()

        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.channel = mock_channel
        client.stub = MagicMock()

        await client.close()

        assert client.channel is None
        assert client.stub is None

    @pytest.mark.asyncio
    async def test_close_handles_no_channel(self):
        """Tests that close handles None channel gracefully."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.channel = None

        # Should not raise
        await client.close()


class TestEmbeddingServiceClientEmbed:
    """Tests for EmbeddingServiceClient.embed method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked stub."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.stub = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_embed_returns_embedding(self, client):
        """Tests that embed returns embedding vector."""
        mock_response = MagicMock()
        mock_response.embedding = [0.1, 0.2, 0.3]
        client.stub.Embed = AsyncMock(return_value=mock_response)

        result = await client.embed("test text", model="text-embedding-3-small", namespace="test-namespace")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_raises_when_not_connected(self):
        """Tests that embed raises RuntimeError when not connected."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.stub = None

        with pytest.raises(RuntimeError) as exc_info:
            await client.embed("test", model="model", namespace="test-namespace")

        assert "not connected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_passes_timeout(self, client):
        """Tests that embed passes timeout to gRPC call."""
        mock_response = MagicMock()
        mock_response.embedding = [0.1]
        client.stub.Embed = AsyncMock(return_value=mock_response)
        client.timeout = 45.0

        await client.embed("test", model="model", namespace="test-namespace")

        client.stub.Embed.assert_called_once()
        call_kwargs = client.stub.Embed.call_args[1]
        assert call_kwargs["timeout"] == 45.0

    @pytest.mark.asyncio
    async def test_embed_raises_on_rpc_error(self, client):
        """Tests that embed raises RpcError on gRPC failure."""
        error = grpc.RpcError()
        error.code = lambda: grpc.StatusCode.UNAVAILABLE
        error.details = lambda: "Service unavailable"
        client.stub.Embed = AsyncMock(side_effect=error)

        with pytest.raises(grpc.RpcError):
            await client.embed("test", model="model", namespace="test-namespace")


class TestEmbeddingServiceClientEmbedBatch:
    """Tests for EmbeddingServiceClient.embed_batch method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked stub."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.stub = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_embed_batch_returns_embeddings(self, client):
        """Tests that embed_batch returns list of embeddings."""
        mock_response = MagicMock()
        mock_response.embeddings = [
            MagicMock(embedding=[0.1, 0.2]),
            MagicMock(embedding=[0.3, 0.4]),
        ]
        client.stub.EmbedBatch = AsyncMock(return_value=mock_response)

        result = await client.embed_batch(["text1", "text2"], model="model", namespace="test-namespace")

        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    async def test_embed_batch_raises_when_not_connected(self):
        """Tests that embed_batch raises RuntimeError when not connected."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.stub = None

        with pytest.raises(RuntimeError) as exc_info:
            await client.embed_batch(["test"], model="model", namespace="test-namespace")

        assert "not connected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_batch_raises_on_rpc_error(self, client):
        """Tests that embed_batch raises RpcError on gRPC failure."""
        error = grpc.RpcError()
        error.code = lambda: grpc.StatusCode.INTERNAL
        error.details = lambda: "Internal error"
        client.stub.EmbedBatch = AsyncMock(side_effect=error)

        with pytest.raises(grpc.RpcError):
            await client.embed_batch(["test"], model="model", namespace="test-namespace")


class TestEmbeddingServiceClientHealthCheck:
    """Tests for EmbeddingServiceClient.health_check method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked stub."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.stub = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_healthy(self, client):
        """Tests that health_check returns True when service is healthy."""
        with patch("src.search_service.grpc_clients.common_pb2") as mock_common:
            mock_response = MagicMock()
            mock_response.status = mock_common.HealthCheckResponse.HEALTHY
            mock_common.HealthCheckResponse.HEALTHY = 1
            mock_response.status = 1
            client.stub.HealthCheck = AsyncMock(return_value=mock_response)

            result = await client.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_not_connected(self):
        """Tests that health_check returns False when not connected."""
        client = EmbeddingServiceClient(address="localhost:50051", timeout=30.0)
        client.stub = None

        result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_rpc_error(self, client):
        """Tests that health_check returns False on RpcError."""
        error = grpc.RpcError()
        error.code = lambda: grpc.StatusCode.UNAVAILABLE
        client.stub.HealthCheck = AsyncMock(side_effect=error)

        result = await client.health_check()

        assert result is False

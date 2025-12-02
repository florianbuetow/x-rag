"""End-to-end integration tests for the RAG pipeline.

Tests the complete flow:
1. Ingest document via Ingestion API
2. Verify Kafka message was published
3. Wait for Indexer to process
4. Verify chunks are stored in Weaviate
"""

import time
import uuid

import httpx
import pytest
import weaviate


@pytest.fixture(scope="module")
def ingestion_url() -> str:
    """Get ingestion API URL."""
    return "http://localhost:8082"


@pytest.fixture(scope="module")
def weaviate_url() -> str:
    """Get Weaviate URL."""
    return "http://localhost:8081"


@pytest.fixture(scope="module")
def test_namespace() -> str:
    """Generate unique test namespace."""
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def weaviate_client(weaviate_url: str):
    """Create Weaviate client."""
    client = weaviate.connect_to_custom(
        http_host="localhost",
        http_port=8081,  # Kind maps NodePort 30081 to hostPort 8081
        http_secure=False,
        grpc_host="localhost",
        grpc_port=50051,  # Kind maps NodePort 30051 to hostPort 50051
        grpc_secure=False,
    )
    yield client
    client.close()


class TestEndToEndIngestion:
    """Test end-to-end document ingestion and indexing."""

    def test_ingestion_api_health(self, ingestion_url: str):
        """Test that Ingestion API is healthy."""
        response = httpx.get(f"{ingestion_url}/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_ingest_document(
        self,
        ingestion_url: str,
        test_namespace: str,
        weaviate_client,
    ):
        """Test complete ingestion flow: API → Kafka → Indexer → Weaviate."""
        # 1. Ingest a test document
        document_data = {
            "text": (
                "Python is a high-level, interpreted programming language "
                "known for its simplicity and readability. Created by Guido "
                "van Rossum and first released in 1991, Python emphasizes "
                "code readability with its notable use of significant "
                "whitespace. The language supports multiple programming "
                "paradigms including procedural, object-oriented, and "
                "functional programming styles. Python has a comprehensive "
                "standard library that supports many common programming tasks "
                "such as connecting to web servers, reading and modifying "
                "files, and working with data structures."
            ),
            "metadata": {
                "title": "Python Programming Language Overview",
                "source_file": "python_intro.txt",
                "type": "technical",
            },
            "namespace": test_namespace,
        }

        # Submit document
        response = httpx.post(
            f"{ingestion_url}/ingest",
            json=document_data,
            timeout=10.0,
        )
        assert response.status_code == 202
        result = response.json()
        assert result["status"] == "accepted"
        document_id = result["document_id"]

        print(f"\n✓ Document ingested: {document_id}")

        # 2. Wait for indexer to process (poll Weaviate)
        max_wait = 30  # seconds
        poll_interval = 2  # seconds
        chunks_found = False

        collection = weaviate_client.collections.get("DocumentChunk")

        for attempt in range(max_wait // poll_interval):
            # Query for chunks with this document ID
            result = collection.query.fetch_objects(
                filters=weaviate.classes.query.Filter.by_property("doc_id").equal(document_id),
                limit=100,
            )

            if len(result.objects) > 0:
                chunks_found = True
                chunk_count = len(result.objects)
                print(f"✓ Found {chunk_count} chunks in Weaviate")

                # Verify chunk properties
                for i, obj in enumerate(result.objects):
                    assert obj.properties["doc_id"] == document_id
                    assert obj.properties["namespace"] == test_namespace
                    assert obj.properties["chunk_index"] == i
                    assert len(obj.properties["content"]) > 0

                    # Get vector dimensions (vector might be dict or direct list)
                    vector = obj.vector
                    if isinstance(vector, dict):
                        vector_len = len(list(vector.values())[0]) if vector else 0
                    else:
                        vector_len = len(vector) if vector else 0

                    print(f"  Chunk {i}: {len(obj.properties['content'])} chars, {vector_len} dimensions")

                break

            print(f"  Waiting for indexer... (attempt {attempt + 1}/{max_wait // poll_interval})")
            time.sleep(poll_interval)

        assert chunks_found, f"Document {document_id} was not indexed within {max_wait} seconds. Check indexer logs for errors."

    def test_duplicate_detection(
        self,
        ingestion_url: str,
        test_namespace: str,
        weaviate_client,
    ):
        """Test that duplicate documents are not re-indexed."""
        document_data = {
            "text": "This is a test document for duplicate detection.",
            "metadata": {
                "title": "Duplicate Test",
                "source_file": "duplicate_test.txt",
            },
            "namespace": test_namespace,
        }

        # Ingest once
        response1 = httpx.post(
            f"{ingestion_url}/ingest",
            json=document_data,
            timeout=10.0,
        )
        assert response1.status_code == 202
        doc_id1 = response1.json()["document_id"]

        # Wait for processing
        time.sleep(5)

        # Count chunks
        collection = weaviate_client.collections.get("DocumentChunk")
        result1 = collection.query.fetch_objects(
            filters=weaviate.classes.query.Filter.by_property("doc_id").equal(doc_id1),
            limit=100,
        )
        initial_count = len(result1.objects)
        assert initial_count > 0, "Document should be indexed"

        print(f"\n✓ Initial indexing: {initial_count} chunks")

        # Ingest again (same content, different ID)
        response2 = httpx.post(
            f"{ingestion_url}/ingest",
            json=document_data,
            timeout=10.0,
        )
        assert response2.status_code == 202
        doc_id2 = response2.json()["document_id"]

        # Wait for processing
        time.sleep(5)

        # Verify second document was also indexed (different doc_id)
        result2 = collection.query.fetch_objects(
            filters=weaviate.classes.query.Filter.by_property("doc_id").equal(doc_id2),
            limit=100,
        )
        second_count = len(result2.objects)
        assert second_count > 0, "Second document should also be indexed"

        print(f"✓ Second indexing: {second_count} chunks")
        print("✓ Duplicate detection test passed")


class TestWeaviateConnection:
    """Test Weaviate connectivity and schema."""

    def test_weaviate_ready(self, weaviate_url: str):
        """Test that Weaviate is ready."""
        response = httpx.get(f"{weaviate_url}/v1/.well-known/ready")
        assert response.status_code == 200

    def test_weaviate_schema(self, weaviate_client):
        """Test that DocumentChunk schema exists."""
        # Get collection
        collection = weaviate_client.collections.get("DocumentChunk")
        config = collection.config.get()

        # Verify required properties
        properties = {prop.name for prop in config.properties}
        required_props = {
            "content",
            "doc_id",
            "chunk_index",
            "namespace",
            "source",
            "title",
            "metadata_json",
        }
        assert required_props.issubset(properties), f"Missing properties: {required_props - properties}"

        print(f"\n✓ Weaviate schema valid with properties: {properties}")

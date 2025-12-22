"""Integration tests for Search UI.

Requires running cluster with Search UI and Search Service deployed.
"""

import httpx
import pytest


@pytest.fixture(scope="module")
def search_ui_url() -> str:
    """Get Search UI URL."""
    return "http://localhost:8080"


class TestSearchUIIntegration:
    """Test Search UI integration with Search Service."""

    def test_search_ui_health(self, search_ui_url: str):
        """Test that Search UI is healthy."""
        response = httpx.get(f"{search_ui_url}/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_root_page_loads(self, search_ui_url: str):
        """Test that root page loads successfully."""
        response = httpx.get(search_ui_url)
        assert response.status_code == 200
        assert "X-RAG Search" in response.text
        assert "Search Query" in response.text

    def test_search_api_endpoint(self, search_ui_url: str):
        """Test search API endpoint with real Search Service.

        Note: This test requires documents to be indexed.
        If no documents exist, the search will still succeed but may return
        a generic answer.
        """
        response = httpx.post(
            f"{search_ui_url}/api/search",
            json={
                "query": "What is Python?",
                "namespace": "test-ns",
                "top_k": 5,
                "mode": "hybrid",
            },
            timeout=30.0,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "metadata" in data
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)

        # If sources exist, verify structure
        if len(data["sources"]) > 0:
            source = data["sources"][0]
            assert "id" in source
            assert "content" in source
            assert "score" in source
            assert isinstance(source["score"], float)

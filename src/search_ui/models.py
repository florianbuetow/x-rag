"""Pydantic models for Search UI."""

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    """Search request model."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    namespace: str = Field(default="default", pattern="^[a-z0-9-]+$", description="Search namespace")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    mode: str = Field(default="hybrid", description="Search mode: vector, bm25, or hybrid")


class Source(BaseModel):
    """Search result source."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Document chunk ID")
    content: str = Field(..., description="Chunk content")
    score: float = Field(..., description="Relevance score")
    metadata: dict[str, str] = Field(default_factory=dict, description="Source metadata")


class SearchResponse(BaseModel):
    """Search response model."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(..., description="Generated answer")
    sources: list[Source] = Field(..., description="Source documents")
    metadata: dict[str, str] = Field(default_factory=dict, description="Search metadata")

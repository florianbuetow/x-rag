"""Evaluation dataset loading and saving.

Provides data classes and functions for managing evaluation datasets.
Datasets are stored as JSON files with a standardized schema.

Dataset format:
{
    "name": "dataset-name",
    "version": "1.0.0",
    "created_at": "2024-12-05T10:00:00Z",
    "chunk_config": {
        "lines_per_chunk": 100,
        "chunk_step": 50
    },
    "samples": [
        {
            "sample_id": "unique-id",
            "question": "What is...?",
            "answer": "The answer is...",
            "source_file": "source.txt",
            "chunk_num": 7,
            "line_start": 301,
            "line_end": 400,
            "chunk_id": "namespace:doc_id:chunk_7",
            "relevant_chunk_ids": ["namespace:doc_id:chunk_7"]
        }
    ],
    "metadata": {
        "total_samples": 150,
        "total_source_files": 20,
        "qa_source_dir": "data/qa/..."
    }
}
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChunkConfig:
    """Configuration for how chunks were created.

    This matches the chunking parameters used in QA generation.
    """

    lines_per_chunk: int
    chunk_step: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "lines_per_chunk": self.lines_per_chunk,
            "chunk_step": self.chunk_step,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChunkConfig:
        """Create from dictionary."""
        return cls(
            lines_per_chunk=data["lines_per_chunk"] if "lines_per_chunk" in data else 100,
            chunk_step=data["chunk_step"] if "chunk_step" in data else 50,
        )


@dataclass(frozen=True)
class EvalSample:
    """A single evaluation sample (question with ground truth).

    Each sample contains a question and the IDs of chunks that are
    relevant to answering that question.
    """

    sample_id: str
    question: str
    relevant_chunk_ids: tuple[str, ...]
    answer: str | None = None
    source_file: str | None = None
    chunk_num: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    chunk_id: str | None = None  # Primary chunk (may differ from relevant_chunk_ids)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "sample_id": self.sample_id,
            "question": self.question,
            "relevant_chunk_ids": list(self.relevant_chunk_ids),
        }
        if self.answer is not None:
            result["answer"] = self.answer
        if self.source_file is not None:
            result["source_file"] = self.source_file
        if self.chunk_num is not None:
            result["chunk_num"] = self.chunk_num
        if self.line_start is not None:
            result["line_start"] = self.line_start
        if self.line_end is not None:
            result["line_end"] = self.line_end
        if self.chunk_id is not None:
            result["chunk_id"] = self.chunk_id
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalSample:
        """Create from dictionary."""
        return cls(
            sample_id=data["sample_id"],
            question=data["question"],
            relevant_chunk_ids=tuple(data["relevant_chunk_ids"] if "relevant_chunk_ids" in data else []),
            answer=data["answer"] if "answer" in data else None,
            source_file=data["source_file"] if "source_file" in data else None,
            chunk_num=data["chunk_num"] if "chunk_num" in data else None,
            line_start=data["line_start"] if "line_start" in data else None,
            line_end=data["line_end"] if "line_end" in data else None,
            chunk_id=data["chunk_id"] if "chunk_id" in data else None,
            metadata=data["metadata"] if "metadata" in data else {},
        )


@dataclass(frozen=True)
class EvalDataset:
    """A complete evaluation dataset.

    Contains multiple evaluation samples and metadata about the dataset.
    """

    name: str
    samples: tuple[EvalSample, ...]
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    chunk_config: ChunkConfig = field(default_factory=ChunkConfig)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Return number of samples."""
        return len(self.samples)

    def __iter__(self) -> Iterator[EvalSample]:
        """Iterate over samples."""
        return iter(self.samples)

    def __getitem__(self, idx: int) -> EvalSample:
        """Get sample by index."""
        return self.samples[idx]

    @property
    def questions(self) -> list[str]:
        """Get all questions."""
        return [s.question for s in self.samples]

    @property
    def relevant_ids(self) -> list[set[str]]:
        """Get relevant chunk IDs for each sample."""
        return [set(s.relevant_chunk_ids) for s in self.samples]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at,
            "chunk_config": self.chunk_config.to_dict(),
            "samples": [s.to_dict() for s in self.samples],
            "metadata": {
                "total_samples": len(self.samples),
                **self.metadata,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalDataset:
        """Create from dictionary."""
        samples = tuple(EvalSample.from_dict(s) for s in (data["samples"] if "samples" in data else []))
        chunk_config = ChunkConfig.from_dict(data["chunk_config"] if "chunk_config" in data else {})
        metadata = data["metadata"] if "metadata" in data else {}
        # Remove auto-generated fields from metadata
        metadata.pop("total_samples", None)

        return cls(
            name=data["name"],
            version=data["version"] if "version" in data else "1.0.0",
            created_at=data["created_at"] if "created_at" in data else datetime.utcnow().isoformat() + "Z",
            chunk_config=chunk_config,
            samples=samples,
            metadata=metadata,
        )

    def filter(self, predicate: callable) -> EvalDataset:
        """Create a new dataset with filtered samples.

        Args:
            predicate: Function that takes EvalSample and returns bool

        Returns:
            New EvalDataset with only samples where predicate is True
        """
        filtered = tuple(s for s in self.samples if predicate(s))
        return EvalDataset(
            name=self.name,
            version=self.version,
            created_at=self.created_at,
            chunk_config=self.chunk_config,
            samples=filtered,
            metadata=self.metadata,
        )

    def sample(self, n: int, seed: int | None) -> EvalDataset:
        """Create a new dataset with a random sample of samples.

        Args:
            n: Number of samples to include
            seed: Random seed for reproducibility

        Returns:
            New EvalDataset with n randomly selected samples
        """
        import random

        if seed is not None:
            random.seed(seed)

        if n >= len(self.samples):
            return self

        sampled = tuple(random.sample(list(self.samples), n))
        return EvalDataset(
            name=f"{self.name}:sample-{n}",
            version=self.version,
            created_at=datetime.utcnow().isoformat() + "Z",
            chunk_config=self.chunk_config,
            samples=sampled,
            metadata={**self.metadata, "sampled_from": self.name, "sample_size": n},
        )


def load_dataset(path: str | Path) -> EvalDataset:
    """Load an evaluation dataset from JSON file.

    Args:
        path: Path to dataset JSON file

    Returns:
        EvalDataset instance

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
        KeyError: If required fields are missing
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return EvalDataset.from_dict(data)


def save_dataset(dataset: EvalDataset, path: str | Path) -> None:
    """Save an evaluation dataset to JSON file.

    Args:
        dataset: EvalDataset to save
        path: Path to save to (will create parent directories)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(dataset.to_dict(), f, indent=2, ensure_ascii=False)

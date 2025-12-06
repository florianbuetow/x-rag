"""Evaluation dataset management.

Provides classes and functions for loading, saving, and managing
evaluation datasets for RAG retrieval evaluation.
"""

from evals.datasets.loader import (
    ChunkConfig,
    EvalDataset,
    EvalSample,
    load_dataset,
    save_dataset,
)

__all__ = [
    "EvalDataset",
    "EvalSample",
    "ChunkConfig",
    "load_dataset",
    "save_dataset",
]

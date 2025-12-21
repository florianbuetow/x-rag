"""Ingestion configuration for dataset chunking strategies."""

from __future__ import annotations

from typing import Any

from src.common.config import Config


class IngestionConfig(Config):
    """Configuration for ingestion and chunking strategies.

    Loads from config/ingestion_config.yaml and provides getter methods
    for chunking parameters per dataset.

    Example:
        config = IngestionConfig.from_yaml("config/ingestion_config.yaml")
        chunking = config.get_chunking("nutritionfacts.org")
        chunk_size = config.get_chunk_size("nutritionfacts.org")
    """

    def get_chunking(self, dataset_name: str) -> dict[str, Any]:
        """Get chunking configuration for a dataset.

        Args:
            dataset_name: Dataset name

        Returns:
            Chunking configuration dict with keys: chunk_method, chunk_size, chunk_overlap

        Raises:
            ConfigurationError: If dataset not found or chunking config missing
        """
        return self.get_dataset_value(dataset_name, "chunking")

    def get_chunk_method(self, dataset_name: str) -> str:
        """Get chunk method for a dataset.

        Args:
            dataset_name: Dataset name

        Returns:
            Chunk method (e.g., 'lines')
        """
        return self.get_dataset_value(dataset_name, "chunking", "chunk_method")

    def get_chunk_size(self, dataset_name: str) -> int:
        """Get chunk size for a dataset.

        Args:
            dataset_name: Dataset name

        Returns:
            Chunk size
        """
        return self.get_dataset_value(dataset_name, "chunking", "chunk_size")

    def get_chunk_overlap(self, dataset_name: str) -> int:
        """Get chunk overlap for a dataset.

        Args:
            dataset_name: Dataset name

        Returns:
            Chunk overlap
        """
        return self.get_dataset_value(dataset_name, "chunking", "chunk_overlap")

    def get_input_path(self, dataset_name: str) -> str:
        """Get input path for a dataset.

        Args:
            dataset_name: Dataset name

        Returns:
            Input path
        """
        return self.get_dataset_value(dataset_name, "input_path")

    def get_namespace(self, dataset_name: str) -> str:
        """Get namespace for a dataset.

        Args:
            dataset_name: Dataset name

        Returns:
            Namespace
        """
        return self.get_dataset_value(dataset_name, "namespace")

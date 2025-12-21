"""Evaluation configuration for RAG evaluation datasets."""

from __future__ import annotations

from typing import Any

from src.common.config import Config


class EvalsConfig(Config):
    """Configuration for RAG evaluation datasets and settings.

    Loads from config/evals_config.yaml and provides getter methods
    for evaluation parameters per dataset.

    Example:
        config = EvalsConfig.from_yaml("config/evals_config.yaml")
        embedding = config.get_embedding("nutritionfacts.org", config_slug="local-bge")
        search_params = config.get_search("nutritionfacts.org")
    """

    def get_embedding(self, dataset_name: str, config_slug: str | None = None) -> dict[str, Any]:
        """Get embedding configuration for a dataset.

        Args:
            dataset_name: Dataset name
            config_slug: Optional config variant slug

        Returns:
            Embedding configuration dict

        Raises:
            ConfigurationError: If dataset not found or embedding config missing
        """
        return self.get_dataset_value(dataset_name, "embedding", config_slug=config_slug)

    def get_search(self, dataset_name: str, config_slug: str | None = None) -> dict[str, Any]:
        """Get search configuration for a dataset.

        Args:
            dataset_name: Dataset name
            config_slug: Optional config variant slug

        Returns:
            Search configuration dict

        Raises:
            ConfigurationError: If dataset not found or search config missing
        """
        return self.get_dataset_value(dataset_name, "search", config_slug=config_slug)

    def get_output(self, dataset_name: str, config_slug: str | None = None) -> dict[str, Any]:
        """Get output configuration for a dataset.

        Args:
            dataset_name: Dataset name
            config_slug: Optional config variant slug

        Returns:
            Output configuration dict

        Raises:
            ConfigurationError: If dataset not found or output config missing
        """
        return self.get_dataset_value(dataset_name, "output", config_slug=config_slug)

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

    def get_collection(self, dataset_name: str) -> str:
        """Get collection name for a dataset.

        Args:
            dataset_name: Dataset name

        Returns:
            Collection name
        """
        return self.get_dataset_value(dataset_name, "collection")

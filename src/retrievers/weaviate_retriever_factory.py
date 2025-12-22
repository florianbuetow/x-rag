"""Factory for creating Weaviate retrievers from configuration."""

from src.common.dataset_config import DatasetsConfigLoader
from src.retrievers.weaviate_retriever import WeaviateRetriever


class WeaviateRetrieverFactory:
    """Factory for creating WeaviateRetriever instances from dataset configs."""

    def __init__(self, datasets_config_path: str, weaviate_url: str) -> None:
        """Initialize factory.

        Args:
            datasets_config_path: Path to datasets configuration YAML file
            weaviate_url: Weaviate server URL
        """
        self.datasets_loader = DatasetsConfigLoader(datasets_config_path)
        self.weaviate_url = weaviate_url

    def create_retriever(self, namespace: str) -> WeaviateRetriever:
        """Create a WeaviateRetriever for the specified namespace.

        Args:
            namespace: Dataset namespace

        Returns:
            Configured WeaviateRetriever instance

        Raises:
            ValueError: If namespace not found in config
        """
        dataset_config = self.datasets_loader.get_dataset_config(namespace)

        retriever = WeaviateRetriever(
            weaviate_url=self.weaviate_url,
            collection_name=dataset_config.weaviate.collection,
            timeout_init=dataset_config.weaviate.timeout_init,
            timeout_query=dataset_config.weaviate.timeout_query,
            timeout_insert=dataset_config.weaviate.timeout_insert,
        )

        return retriever

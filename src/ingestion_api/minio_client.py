"""Thin wrapper for MinIO client."""

import logging
from io import BytesIO

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinioClient:
    """Thin wrapper around MinIO client with health check."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ):
        """Initialize MinIO client.

        Args:
            endpoint: MinIO endpoint (with or without http://)
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Bucket name for document storage
            secure: Whether to use HTTPS
        """
        self.bucket = bucket
        # Remove http:// or https:// prefix for Minio client
        clean_endpoint = endpoint.replace("http://", "").replace("https://", "")
        self.client = Minio(
            clean_endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create bucket if it doesn't exist.

        Raises:
            S3Error: If bucket creation fails
        """
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")
            else:
                logger.info(f"MinIO bucket exists: {self.bucket}")
        except S3Error as e:
            logger.error(f"Failed to ensure bucket: {e}")
            raise

    def store_document(self, object_name: str, content: bytes) -> str:
        """Store document in MinIO.

        Args:
            object_name: Object key (e.g., "uuid.json")
            content: Document content as bytes

        Returns:
            Object name that was stored

        Raises:
            S3Error: If storage fails
        """
        try:
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=BytesIO(content),
                length=len(content),
                content_type="application/json",
            )
            logger.debug(f"Stored document: {object_name} ({len(content)} bytes)")
            return object_name
        except S3Error as e:
            logger.error(f"Failed to store document {object_name}: {e}")
            raise

    async def health_check(self) -> bool:
        """Check MinIO connectivity.

        Returns:
            True if healthy, False otherwise
        """
        try:
            self.client.bucket_exists(self.bucket)
            return True
        except Exception as e:
            logger.debug(f"MinIO health check failed: {e}")
            return False

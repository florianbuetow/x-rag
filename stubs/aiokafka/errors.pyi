"""Type stubs for aiokafka.errors module."""

class KafkaError(Exception):
    """Base class for Kafka errors."""
    ...

class KafkaConnectionError(KafkaError):
    """Kafka connection error."""
    ...

class KafkaTimeoutError(KafkaError):
    """Kafka timeout error."""
    ...

class ProducerClosed(KafkaError):
    """Producer is closed."""
    ...

class RequestTimedOutError(KafkaError):
    """Request timed out."""
    ...

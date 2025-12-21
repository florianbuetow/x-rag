# Configuration Unification Plan

## Overview

This plan outlines the refactoring strategy to unify configuration classes across all services. The goal is to create a consistent, reusable, and validated configuration system using Pydantic models with composition.

## Current State Analysis

### Current Structure
- **Base Config**: `src/common/config.py` contains `BaseConfig` and `ServiceConfig`
- **Service Configs**: Each service has its own config file (e.g., `src/search_service/config.py`)
- **Unused Config Classes**: `RedisConfig`, `KafkaConfig`, `OpenAIConfig` exist but are not used
- **Pattern**: Services define fields directly instead of composing reusable config models

### Problems
1. **Code Duplication**: Kafka, Redis, OpenAI configs are duplicated across services
2. **Inconsistent Validation**: Each service implements its own validation logic
3. **No Reusability**: Config models exist but aren't used
4. **Missing Composition**: Services don't leverage reusable config components

## Target Architecture

### Design Principles

1. **Composition over Inheritance**: Use Pydantic models as building blocks
2. **Single Source of Truth**: Each config type (Kafka, Redis, etc.) defined once
3. **Getter Methods**: Service configs expose composed configs via getter methods
4. **Centralized Validation**: Base class provides validation framework
5. **Type Safety**: Full Pydantic validation at every level

### Architecture Overview

```
BaseConfig (Pydantic BaseSettings)
  └── ServiceConfig (common service fields)
      └── [Service]Config (service-specific config)
          ├── get_kafka_config() -> KafkaConfig
          ├── get_redis_config() -> RedisConfig
          ├── get_openai_config() -> OpenAIConfig
          └── validate() -> ValidationResult
```

## Implementation Plan

### Phase 1: Refactor Common Config Models

**File**: `src/common/config.py`

**Changes**:
1. Keep `BaseConfig` and `ServiceConfig` as-is
2. Refactor `RedisConfig`, `KafkaConfig`, `OpenAIConfig` to be standalone Pydantic models (not BaseConfig subclasses)
3. Add `WeaviateConfig` as a standalone model
4. Add validation helper methods to base class

**New Structure**:
```python
# Standalone Pydantic models (not BaseSettings)
class KafkaConfig(BaseModel):
    """Kafka connection configuration."""
    kafka_bootstrap: str = Field(default="kafka:9092", ...)
    kafka_topic: str = Field(default="document-changes", ...)
    kafka_group_id: str | None = Field(default=None, ...)
    kafka_acks: str = Field(default="1", ...)
    kafka_auto_offset_reset: str = Field(default="earliest", ...)
    
    @field_validator("kafka_bootstrap")
    @classmethod
    def validate_bootstrap(cls, v: str) -> str:
        # Validation logic
        return v

class RedisConfig(BaseModel):
    """Redis connection configuration."""
    redis_url: str = Field(default="redis://redis:6379", ...)
    cache_ttl: int = Field(default=3600, ge=0, ...)
    enable_cache: bool = Field(default=True, ...)
    
    @field_validator("redis_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith("redis://"):
            raise ValueError(f"Invalid Redis URL '{v}'")
        return v

class OpenAIConfig(BaseModel):
    """OpenAI API configuration."""
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_api_base: str | None = Field(default=None, ...)
    openai_model: str = Field(default="gpt-4o-mini", ...)
    openai_max_tokens: int = Field(default=500, ge=1, le=32000, ...)
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0, ...)
    openai_max_retries: int = Field(default=3, ge=0, ...)
    openai_timeout: int = Field(default=60, ge=1, ...)
    
    @field_validator("openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "sk-your-key-here":
            raise ValueError("OpenAI API key not configured")
        # For local LLMs, any non-empty key is valid
        return v

class WeaviateConfig(BaseModel):
    """Weaviate connection configuration."""
    weaviate_url: str = Field(default="http://weaviate:8080", ...)
    weaviate_timeout: int = Field(default=30, ge=1, ...)
    weaviate_collection: str = Field(default="DocumentChunk", ...)
    
    @field_validator("weaviate_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid Weaviate URL '{v}'")
        return v.rstrip("/")
```

### Phase 2: Add Base Config Validation Framework

**File**: `src/common/config.py`

**Add to BaseConfig**:
```python
from typing import Any
from pydantic import ValidationError

class BaseConfig(BaseSettings):
    # ... existing code ...
    
    def validate_config(self) -> dict[str, Any]:
        """Validate the entire configuration object.
        
        Returns:
            Dictionary with validation results:
            {
                "valid": bool,
                "errors": list[str],
                "warnings": list[str]
            }
        """
        errors: list[str] = []
        warnings: list[str] = []
        
        try:
            # Pydantic validation happens at instantiation
            # This method can perform additional cross-field validation
            self._validate_cross_fields(errors, warnings)
        except ValidationError as e:
            errors.extend(str(err) for err in e.errors())
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_cross_fields(self, errors: list[str], warnings: list[str]) -> None:
        """Override in subclasses for cross-field validation."""
        pass
    
    def get_config_dict(self) -> dict[str, Any]:
        """Get all configuration as a dictionary.
        
        Returns:
            Dictionary of all configuration values
        """
        return self.model_dump()
```

### Phase 3: Refactor Service Configs

**Pattern for each service config**:

```python
# Example: src/search_service/config.py
from src.common.config import ServiceConfig, KafkaConfig, RedisConfig, OpenAIConfig, WeaviateConfig

class SearchServiceConfig(ServiceConfig):
    """Search Service configuration."""
    
    # Service-specific fields
    service_name: str = Field(default="search-service", ...)
    port: int = Field(default=50052, ...)
    enable_reflection: bool = Field(default=True, ...)
    
    # Composed config fields (raw values from env)
    # These will be converted to models via getters
    weaviate_url: str = Field(default="http://weaviate:8080", ...)
    weaviate_timeout: int = Field(default=30, ...)
    weaviate_collection: str = Field(default="DocumentChunk", ...)
    
    redis_url: str | None = Field(default=None, ...)  # Optional
    cache_ttl: int = Field(default=3600, ...)
    enable_cache: bool = Field(default=True, ...)
    
    openai_api_key: str = Field(..., ...)
    openai_api_base: str | None = Field(default=None, ...)
    openai_model: str = Field(default="gpt-4o-mini", ...)
    openai_max_tokens: int = Field(default=500, ...)
    openai_temperature: float = Field(default=0.7, ...)
    openai_max_retries: int = Field(default=3, ...)
    openai_timeout: int = Field(default=60, ...)
    
    # ... other service-specific fields ...
    
    # Getter methods for composed configs
    def get_weaviate_config(self) -> WeaviateConfig:
        """Get Weaviate configuration as a validated model."""
        return WeaviateConfig(
            weaviate_url=self.weaviate_url,
            weaviate_timeout=self.weaviate_timeout,
            weaviate_collection=self.weaviate_collection,
        )
    
    def get_redis_config(self) -> RedisConfig | None:
        """Get Redis configuration if enabled."""
        if not self.enable_cache or not self.redis_url:
            return None
        return RedisConfig(
            redis_url=self.redis_url,
            cache_ttl=self.cache_ttl,
            enable_cache=self.enable_cache,
        )
    
    def get_openai_config(self) -> OpenAIConfig:
        """Get OpenAI configuration as a validated model."""
        return OpenAIConfig(
            openai_api_key=self.openai_api_key,
            openai_api_base=self.openai_api_base,
            openai_model=self.openai_model,
            openai_max_tokens=self.openai_max_tokens,
            openai_temperature=self.openai_temperature,
            openai_max_retries=self.openai_max_retries,
            openai_timeout=self.openai_timeout,
        )
    
    def _validate_cross_fields(self, errors: list[str], warnings: list[str]) -> None:
        """Validate cross-field dependencies."""
        # Example: If cache is enabled, redis_url must be set
        if self.enable_cache and not self.redis_url:
            errors.append("redis_url is required when enable_cache is True")
        
        # Validate composed configs
        try:
            self.get_weaviate_config()
        except ValidationError as e:
            errors.extend(f"Weaviate config: {err}" for err in e.errors())
        
        try:
            self.get_openai_config()
        except ValidationError as e:
            errors.extend(f"OpenAI config: {err}" for err in e.errors())
        
        if self.enable_cache:
            try:
                redis_config = self.get_redis_config()
                if redis_config is None:
                    errors.append("Redis config is None but cache is enabled")
            except ValidationError as e:
                errors.extend(f"Redis config: {err}" for err in e.errors())
```

### Phase 4: Service-Specific Config Refactoring

#### 4.1 IndexerConfig (`src/indexer/config.py`)

**Changes**:
- Remove direct Kafka, MinIO, Weaviate field definitions
- Add getter methods: `get_kafka_config()`, `get_weaviate_config()`
- Add `MinIOConfig` model to common config
- Use composed configs via getters

**New MinIOConfig**:
```python
class MinIOConfig(BaseModel):
    """MinIO storage configuration."""
    minio_endpoint: str = Field(..., ...)
    minio_access_key: str = Field(..., ...)
    minio_secret_key: str = Field(..., ...)
    minio_bucket: str = Field(default="documents", ...)
    minio_secure: bool = Field(default=False, ...)
    
    @field_validator("minio_endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        # Normalize endpoint
        if v.startswith(("http://", "https://")):
            return v.rstrip("/")
        return f"http://{v}".rstrip("/")
```

#### 4.2 IngestionAPIConfig (`src/ingestion_api/config.py`)

**Changes**:
- Add `get_kafka_config()` and `get_minio_config()` methods
- Use composed configs

#### 4.3 SearchServiceConfig (`src/search_service/config.py`)

**Changes**:
- Already has some structure, refactor to use:
  - `get_weaviate_config()`
  - `get_redis_config()`
  - `get_openai_config()`
- Keep `get_llm_config()` but have it use `get_openai_config()` internally

#### 4.4 EmbeddingServiceConfig (`src/embedding_service/config.py`)

**Changes**:
- Keep existing `get_embedding_config()` method
- Add `get_openai_config()` if needed
- Ensure consistency with other services

### Phase 5: Update Usage Sites

**Pattern for updating service code**:

```python
# Before:
kafka_client = KafkaClient(
    bootstrap_servers=config.kafka_bootstrap,
    acks=config.kafka_acks,
)

# After:
kafka_config = config.get_kafka_config()
kafka_client = KafkaClient(
    bootstrap_servers=kafka_config.kafka_bootstrap,
    acks=kafka_config.kafka_acks,
)
```

**Files to update**:
- `src/indexer/main.py`
- `src/ingestion_api/main.py`
- `src/search_service/main.py`
- Any other files using config directly

### Phase 6: Testing Strategy

**Update tests** (`tests/test_config.py`):

1. Test each composed config model independently
2. Test getter methods return correct models
3. Test validation works correctly
4. Test cross-field validation
5. Test error messages are helpful

**Example test**:
```python
def test_search_service_config_getters():
    """Test that getter methods return validated configs."""
    config = SearchServiceConfig(
        service_name="test",
        openai_api_key="sk-test",
        weaviate_url="http://localhost:8080",
    )
    
    # Test getters return correct types
    weaviate_config = config.get_weaviate_config()
    assert isinstance(weaviate_config, WeaviateConfig)
    assert weaviate_config.weaviate_url == "http://localhost:8080"
    
    openai_config = config.get_openai_config()
    assert isinstance(openai_config, OpenAIConfig)
    assert openai_config.openai_api_key == "sk-test"
    
    # Test validation
    validation_result = config.validate_config()
    assert validation_result["valid"] is True
```

## Migration Steps

### Step 1: Create New Config Models
1. Refactor `RedisConfig`, `KafkaConfig`, `OpenAIConfig` in `src/common/config.py`
2. Add `MinIOConfig` model
3. Ensure all models inherit from `BaseModel` (not `BaseSettings`)

### Step 2: Add Validation Framework
1. Add `validate_config()` method to `BaseConfig`
2. Add `get_config_dict()` helper method
3. Add `_validate_cross_fields()` hook

### Step 3: Refactor One Service at a Time
1. Start with `IndexerConfig` (simplest)
2. Add getter methods
3. Update usage in `src/indexer/main.py`
4. Update tests
5. Repeat for other services

### Step 4: Clean Up
1. Remove unused config classes if any
2. Update documentation
3. Run full test suite

## Benefits

1. **Reusability**: Config models defined once, used everywhere
2. **Consistency**: Same validation logic across services
3. **Type Safety**: Full Pydantic validation at every level
4. **Maintainability**: Changes to config structure happen in one place
5. **Testability**: Each config model can be tested independently
6. **Documentation**: Clear separation of concerns

## Potential Challenges

1. **Breaking Changes**: Existing code expects direct field access
2. **Migration Effort**: Need to update all service code
3. **Performance**: Creating new model instances on each getter call (minimal impact)
4. **Backward Compatibility**: May need to support both patterns during transition

## Alternative Approach: Cached Getters

If performance is a concern, we can cache the composed configs:

```python
from functools import lru_cache

class SearchServiceConfig(ServiceConfig):
    # ... fields ...
    
    @lru_cache(maxsize=1)
    def get_weaviate_config(self) -> WeaviateConfig:
        """Get Weaviate configuration (cached)."""
        return WeaviateConfig(...)
```

However, since configs are immutable (`frozen=True`), caching may not be necessary.

## Timeline Estimate

- **Phase 1-2**: 2-3 hours (refactor common configs)
- **Phase 3**: 1-2 hours per service (4-6 services = 4-12 hours)
- **Phase 4**: 2-3 hours (update usage sites)
- **Phase 5**: 2-3 hours (update tests)
- **Total**: ~12-21 hours

## Next Steps

1. Review and approve this plan
2. Start with Phase 1 (refactor common config models)
3. Test thoroughly before moving to next phase
4. Iterate based on feedback


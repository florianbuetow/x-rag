# Grafana Alloy Integration Plan

## Overview

Install Grafana Alloy as a unified OpenTelemetry collector in the X-RAG Kubernetes cluster. All services will export metrics via OTLP to Alloy, which forwards them to the existing Prometheus instance.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        X-RAG Kubernetes Cluster                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│   │ search-ui   │  │ search-svc  │  │ ingestion   │  │ embedding   │    │
│   │             │  │             │  │             │  │             │    │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│          │                │                │                │           │
│          │     OTLP/gRPC (metrics)         │                │           │
│          └────────────────┴────────────────┴────────────────┘           │
│                                    │                                     │
│                                    ▼                                     │
│                         ┌─────────────────────┐                          │
│                         │   Grafana Alloy     │                          │
│                         │   (OTLP Receiver)   │                          │
│                         └──────────┬──────────┘                          │
│                                    │                                     │
│                         Prometheus Remote Write                          │
│                                    │                                     │
│                                    ▼                                     │
│                         ┌─────────────────────┐                          │
│                         │    Prometheus       │                          │
│                         └──────────┬──────────┘                          │
│                                    │                                     │
│                                    ▼                                     │
│                         ┌─────────────────────┐                          │
│                         │     Grafana         │                          │
│                         └─────────────────────┘                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Current State

| Component | Status |
|-----------|--------|
| Prometheus | ✅ Running, scraping services directly |
| Grafana | ✅ Running, visualizing Prometheus data |
| Tempo | ✅ Running, receiving OTLP traces |
| Services | ✅ Using prometheus_client, exposing /metrics |
| OTel SDK | ✅ Dependencies in pyproject.toml (not wired up) |

## Target State

| Component | Change |
|-----------|--------|
| Grafana Alloy | 🆕 New deployment, receives OTLP metrics |
| Services | 🔄 Export metrics via OTLP only (removed Prometheus scrape) |
| Prometheus | 🔄 Receive metrics via remote_write from Alloy only |

---

## Implementation Phases

### Phase 1: Deploy Grafana Alloy

**Files to create:**
- `infra/k8s/monitoring/alloy-config.yaml` - ConfigMap with Alloy configuration
- `infra/k8s/monitoring/alloy.yaml` - Deployment + Service

**Alloy Configuration (River language):**

```river
// Receive OTLP metrics from services
otelcol.receiver.otlp "default" {
  grpc {
    endpoint = "0.0.0.0:4317"
  }
  http {
    endpoint = "0.0.0.0:4318"
  }
  output {
    metrics = [otelcol.processor.batch.default.input]
  }
}

// Batch metrics for efficient forwarding
otelcol.processor.batch "default" {
  output {
    metrics = [otelcol.exporter.prometheus.default.input]
  }
}

// Convert OTLP metrics to Prometheus format and expose
otelcol.exporter.prometheus "default" {
  forward_to = [prometheus.remote_write.prom.receiver]
}

// Remote write to Prometheus
prometheus.remote_write "prom" {
  endpoint {
    url = "http://xrag-prometheus:9090/api/v1/write"
  }
}
```

**Kubernetes manifests:**

```yaml
# alloy.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xrag-alloy
  namespace: rag-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: xrag-alloy
  template:
    spec:
      containers:
        - name: alloy
          image: grafana/alloy:v1.4.2
          args:
            - run
            - /etc/alloy/config.alloy
            - --storage.path=/var/lib/alloy/data
          ports:
            - containerPort: 4317  # OTLP gRPC
            - containerPort: 4318  # OTLP HTTP
            - containerPort: 12345 # Alloy UI
---
apiVersion: v1
kind: Service
metadata:
  name: xrag-alloy
  namespace: rag-system
spec:
  ports:
    - name: otlp-grpc
      port: 4317
    - name: otlp-http
      port: 4318
    - name: ui
      port: 12345
```

**Tasks:**
- [ ] Create `infra/k8s/monitoring/alloy-config.yaml`
- [ ] Create `infra/k8s/monitoring/alloy.yaml`
- [ ] Update Prometheus to enable remote_write receiver

---

### Phase 2: Enable Prometheus Remote Write Receiver

**File to modify:** `infra/k8s/monitoring/prometheus.yaml`

Prometheus needs `--web.enable-remote-write-receiver` flag:

```yaml
args:
  - "--config.file=/etc/prometheus/prometheus.yml"
  - "--storage.tsdb.path=/prometheus"
  - "--web.enable-remote-write-receiver"  # NEW
```

**Tasks:**
- [ ] Add remote write receiver flag to Prometheus deployment

---

### Phase 3: Create OTel Metrics Infrastructure Module

**File to create:** `src/common/otel_metrics.py`

This module provides OTel metric export that works alongside existing Prometheus metrics:

```python
"""OpenTelemetry metrics export for services.

Provides OTLP metric export to Grafana Alloy alongside existing
Prometheus metrics. Both systems receive the same metrics.
"""

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

def init_otel_metrics(service_name: str, alloy_endpoint: str = "xrag-alloy:4317") -> None:
    """Initialize OpenTelemetry metrics with OTLP export.
    
    Args:
        service_name: Name of the service for resource attribution
        alloy_endpoint: Grafana Alloy OTLP gRPC endpoint
    """
    resource = Resource.create({SERVICE_NAME: service_name})
    
    exporter = OTLPMetricExporter(
        endpoint=alloy_endpoint,
        insecure=True,  # Within cluster, no TLS
    )
    
    reader = PeriodicExportingMetricReader(
        exporter,
        export_interval_millis=15000,  # Match Prometheus scrape interval
    )
    
    provider = MeterProvider(
        resource=resource,
        metric_readers=[reader],
    )
    
    metrics.set_meter_provider(provider)
```

**Tasks:**
- [ ] Create `src/common/otel_metrics.py`
- [ ] Add configuration for OTLP endpoint

---

### Phase 4: Instrument Services with OTel Metrics

Each service needs to:
1. Call `init_otel_metrics()` at startup
2. Create OTel metrics that mirror existing Prometheus metrics

**Strategy: Dual Export**

Keep existing `prometheus_client` metrics (for backward compatibility) and add parallel OTel metrics:

```python
# src/search_service/main.py
from src.common.otel_metrics import init_otel_metrics
from opentelemetry import metrics

# Initialize OTel on startup
init_otel_metrics("search-service")

# Get meter for this service
meter = metrics.get_meter("search-service")

# Create OTel metrics alongside existing Prometheus metrics
otel_request_duration = meter.create_histogram(
    "search_service_request_duration_seconds",
    description="Total duration of Search Service requests",
    unit="s",
)
```

**Services to update:**

| Service | File | Metrics Module |
|---------|------|----------------|
| search-ui | `src/search_ui/main.py` | `src/search_ui/metrics.py` |
| search-service | `src/search_service/main.py` | `src/search_service/metrics.py` |
| ingestion-api | `src/ingestion_api/main.py` | `src/ingestion_api/metrics.py` |
| embedding-service | `src/embedding_service/main.py` | `src/embedding_service/metrics.py` |
| indexer | `src/indexer/main.py` | `src/indexer/metrics.py` |

**Tasks:**
- [ ] Update `src/search_ui/main.py` - add OTel init
- [ ] Update `src/search_service/main.py` - add OTel init
- [ ] Update `src/ingestion_api/main.py` - add OTel init
- [ ] Update `src/embedding_service/main.py` - add OTel init
- [ ] Update `src/indexer/main.py` - add OTel init
- [ ] Create OTel metric definitions in each service's metrics.py

---

### Phase 5: Environment Configuration

**Files to update:**
- `.env.example` - Add OTLP endpoint config
- Service Kubernetes deployments - Add env vars

```bash
# .env.example
OTEL_EXPORTER_OTLP_ENDPOINT=xrag-alloy:4317
OTEL_METRICS_ENABLED=true
```

**Tasks:**
- [ ] Update `.env.example`
- [ ] Update each service's K8s deployment with OTLP env vars

---

### Phase 6: Testing & Validation

**Validation steps:**
1. Deploy Alloy: `kubectl apply -f infra/k8s/monitoring/alloy.yaml`
2. Verify Alloy is receiving metrics: Check Alloy UI at http://localhost:12345
3. Verify Prometheus receives remote_write: Check Prometheus targets
4. Verify Grafana dashboards still work

**Tasks:**
- [ ] Write integration test for OTel metric export
- [ ] Add Alloy to `make cluster-start` deployment
- [ ] Update docs/METRICS.md with OTel information
- [ ] Validate end-to-end metric flow

---

## Alternative Approaches Considered

### Option A: Replace Prometheus Scrape with OTLP (Chosen: NO)
- Removes scrape configs entirely
- Risk: Breaking change, existing dashboards may break
- Rejected: Too disruptive

### Option B: Dual Export (Chosen: YES)
- Keep Prometheus scrape AND add OTLP export
- Both paths write to same Prometheus
- Allows gradual migration

### Option C: OTel Collector instead of Alloy (Chosen: NO)
- Standard OTel Collector works fine
- Rejected: Alloy has better Grafana ecosystem integration

---

## Dependencies

Already in `pyproject.toml`:
```toml
"opentelemetry-api>=1.20.0",
"opentelemetry-sdk>=1.20.0",
"opentelemetry-exporter-otlp>=1.20.0",
```

No new dependencies required.

---

## Rollback Plan

If issues occur:
1. Remove `init_otel_metrics()` calls from services
2. Delete Alloy deployment: `kubectl delete -f infra/k8s/monitoring/alloy.yaml`
3. Remove `--web.enable-remote-write-receiver` from Prometheus
4. Existing Prometheus scrape continues working

---

## Success Criteria

- [ ] Alloy pod running and healthy
- [ ] All 5 services exporting metrics via OTLP
- [ ] Metrics visible in Prometheus from remote_write source
- [ ] Existing Grafana dashboards continue working
- [ ] `make ci` passes with OTel changes

---

## Estimated Effort

| Phase | Effort |
|-------|--------|
| Phase 1: Deploy Alloy | 1 hour |
| Phase 2: Prometheus Config | 15 min |
| Phase 3: OTel Module | 1 hour |
| Phase 4: Instrument Services | 2 hours |
| Phase 5: Configuration | 30 min |
| Phase 6: Testing | 1 hour |
| **Total** | **~6 hours** |

---

## Next Steps

1. Review this plan
2. Approve or request changes
3. Begin Phase 1 implementation

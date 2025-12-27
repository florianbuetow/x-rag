#!/usr/bin/env just --justfile

set quiet := false

CLUSTER_NAME := "xrag-k8"
NAMESPACE := "rag-system"
REGISTRY_NAME := "xrag-k8-kind-registry"
REGISTRY_PORT := "5000"
REGISTRY_VOLUME := "xrag-registry-data"
PROJECT_ROOT := justfile_directory()

# List available commands
default:
    @just --list

# One-time initialization: build images, setup cluster, shutdown
init:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Checking prerequisites..."
    command -v docker >/dev/null || { echo "Error: docker not found"; exit 1; }
    docker info >/dev/null || { echo "Error: Docker daemon not running"; exit 1; }
    command -v uv >/dev/null || { echo "Error: uv not found"; exit 1; }
    command -v kubectl >/dev/null || { echo "Error: kubectl not found"; exit 1; }
    command -v kind >/dev/null || { echo "Error: kind not found"; exit 1; }
    echo "Prerequisites checked"

    echo "Creating directories..."
    mkdir -p {{ PROJECT_ROOT }}/reports/coverage {{ PROJECT_ROOT }}/reports/security {{ PROJECT_ROOT }}/data/storage
    echo "Directories created"

    echo "Installing dependencies..."
    cd {{ PROJECT_ROOT }} && uv sync --all-extras >/dev/null
    echo "Dependencies installed"

    echo "Creating cluster..."
    {{ PROJECT_ROOT }}/scripts/create-cluster.sh >/dev/null
    echo "Cluster created"

    echo "Creating registry..."
    {{ PROJECT_ROOT }}/scripts/setup-registry.sh >/dev/null
    echo "Registry created"

    echo "Building images..."
    {{ PROJECT_ROOT }}/scripts/build-images.sh >/dev/null
    echo "Images built"

    echo "Pushing images..."
    {{ PROJECT_ROOT }}/scripts/register-images.sh >/dev/null
    echo "Images pushed"

    echo "Tagging base images..."
    # Tag registry image for cleanup (kindest/node is tagged by create-cluster.sh)
    if docker image inspect registry:2 &>/dev/null; then
        docker tag registry:2 xrag/registry:2
    fi
    echo "Base images tagged"

    echo "Shutting down cluster..."
    kind delete cluster --name {{ CLUSTER_NAME }} >/dev/null 2>&1
    docker stop {{ REGISTRY_NAME }} >/dev/null 2>&1
    echo "Init completed"

# Start cluster and deploy all services
start:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Starting cluster..."
    if ! kind get clusters 2>/dev/null | grep -q "^{{ CLUSTER_NAME }}$"; then
        {{ PROJECT_ROOT }}/scripts/create-cluster.sh >/dev/null
    fi
    echo "Cluster started"

    echo "Starting registry..."
    if ! docker inspect {{ REGISTRY_NAME }} &>/dev/null; then
        {{ PROJECT_ROOT }}/scripts/setup-registry.sh >/dev/null
    elif [ "$(docker inspect -f '{{{{.State.Running}}}}' {{ REGISTRY_NAME }} 2>/dev/null)" != "true" ]; then
        docker start {{ REGISTRY_NAME }} >/dev/null
    fi
    echo "Registry started"

    # Deploy infrastructure components individually with progress messages
    echo "Deploying Redis..."
    kubectl apply -f {{ PROJECT_ROOT }}/infra/k8s/redis/ -n {{ NAMESPACE }} >/dev/null 2>&1
    kubectl wait --for=condition=Ready pod -l app=xrag-redis -n {{ NAMESPACE }} --timeout=120s >/dev/null 2>&1
    echo "Redis deployed"

    echo "Deploying MinIO..."
    kubectl apply -f {{ PROJECT_ROOT }}/infra/k8s/minio/ -n {{ NAMESPACE }} >/dev/null 2>&1
    kubectl wait --for=condition=Ready pod -l app=xrag-minio -n {{ NAMESPACE }} --timeout=120s >/dev/null 2>&1
    echo "MinIO deployed"

    echo "Deploying Kafka..."
    kubectl apply -f {{ PROJECT_ROOT }}/infra/k8s/kafka/ -n {{ NAMESPACE }} >/dev/null 2>&1
    kubectl wait --for=condition=Ready pod -l app=xrag-kafka -n {{ NAMESPACE }} --timeout=240s >/dev/null 2>&1
    echo "Kafka deployed"

    echo "Deploying Weaviate..."
    kubectl apply -f {{ PROJECT_ROOT }}/infra/k8s/weaviate/weaviate.yaml -n {{ NAMESPACE }} >/dev/null 2>&1
    kubectl wait --for=condition=Ready pod -l app=xrag-weaviate -n {{ NAMESPACE }} --timeout=240s >/dev/null 2>&1
    kubectl delete job weaviate-schema-init -n {{ NAMESPACE }} --ignore-not-found >/dev/null 2>&1
    kubectl apply -f {{ PROJECT_ROOT }}/infra/k8s/weaviate/schema-init.yaml -n {{ NAMESPACE }} >/dev/null 2>&1
    kubectl wait --for=condition=Complete job/weaviate-schema-init -n {{ NAMESPACE }} --timeout=120s >/dev/null 2>&1
    echo "Weaviate deployed"

    # Load environment variables for app deployment
    if [ -f {{ PROJECT_ROOT }}/.env ]; then
        set -a
        source {{ PROJECT_ROOT }}/.env
        set +a
    fi
    export OPENAI_API_BASE="${OPENAI_API_BASE:-https://api.openai.com/v1}"
    export OPENAI_MODEL="${OPENAI_MODEL:-gpt-4o-mini}"
    export OPENAI_EMBEDDING_MODEL="${OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}"
    export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-your-key-here}"
    if [[ "${OBSERVABILITY_ENABLED:-true}" == "false" ]]; then
        export OTEL_METRICS_ENABLED="false"
    else
        export OTEL_METRICS_ENABLED="true"
    fi

    # Deploy each app individually with progress messages
    SERVICES=($({{ PROJECT_ROOT }}/scripts/list-services.sh))
    for service in "${SERVICES[@]}"; do
        echo "Deploying ${service}..."
        manifest_dir="{{ PROJECT_ROOT }}/infra/k8s/${service}"
        if [ -d "${manifest_dir}" ]; then
            for manifest in "${manifest_dir}"/*.yaml; do
                envsubst '${OPENAI_API_BASE} ${OPENAI_MODEL} ${OPENAI_EMBEDDING_MODEL} ${OPENAI_API_KEY} ${OTEL_METRICS_ENABLED}' < "${manifest}" | kubectl apply -n {{ NAMESPACE }} -f - >/dev/null 2>&1
            done
            if kubectl get deployment "${service}" -n {{ NAMESPACE }} &>/dev/null; then
                kubectl rollout status deployment/"${service}" -n {{ NAMESPACE }} --timeout=120s >/dev/null 2>&1
            fi
        fi
        echo "${service} deployed"
    done

    echo "Start completed"

# Stop cluster and registry
stop:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Stopping cluster..."
    if kind get clusters 2>/dev/null | grep -q "^{{ CLUSTER_NAME }}$"; then
        kind delete cluster --name {{ CLUSTER_NAME }} >/dev/null 2>&1
    fi
    echo "Cluster stopped"

    echo "Stopping registry..."
    if docker inspect {{ REGISTRY_NAME }} &>/dev/null; then
        docker stop {{ REGISTRY_NAME }} >/dev/null 2>&1
    fi
    echo "Registry stopped"

    echo "Stop completed"

# Complete cleanup
destroy: stop
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Deleting registry..."
    if docker inspect {{ REGISTRY_NAME }} &>/dev/null; then
        docker rm -f {{ REGISTRY_NAME }} >/dev/null 2>&1
    fi
    if docker volume inspect {{ REGISTRY_VOLUME }} &>/dev/null; then
        docker volume rm {{ REGISTRY_VOLUME }} >/dev/null 2>&1
    fi
    echo "Registry deleted"

    echo "Deleting venv..."
    if [ -d {{ PROJECT_ROOT }}/.venv ]; then
        rm -rf {{ PROJECT_ROOT }}/.venv
    fi
    echo "Venv deleted"

    echo "Deleting directories..."
    if [ -d {{ PROJECT_ROOT }}/reports/ ]; then
        rm -rf {{ PROJECT_ROOT }}/reports/
    fi
    if [ -d {{ PROJECT_ROOT }}/data/storage ]; then
        rm -rf {{ PROJECT_ROOT }}/data/storage/*
    fi
    echo "Directories deleted"

    echo "Deleting images..."
    IMAGES=$(docker images "xrag/*" -q)
    if [ -n "$IMAGES" ]; then
        docker rmi -f $IMAGES >/dev/null 2>&1
    fi
    echo "Images deleted"

    echo "Destroy completed"

# Run strict type checking with Pyright (LSP-based)
code-lspchecks:
    @echo ""
    @echo "\033[0;34m=== Running Pyright Type Checks ===\033[0m"
    @mkdir -p reports/pyright
    @uv run pyright --project pyrightconfig.json > reports/pyright/pyright.txt 2>&1 || true
    @uv run pyright --project pyrightconfig.json
    @echo ""
    @echo "\033[0;32m✓ Pyright checks passed\033[0m"
    @echo "  Report: reports/pyright/pyright.txt"
    @echo ""

# Run all CI validation checks
ci:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{ PROJECT_ROOT }}

    echo "Running init..."
    make init

    echo "Running test-integration-config..."
    make test-integration-config

    echo "Running code-style..."
    make code-style

    echo "Running code-typecheck..."
    make code-typecheck

    echo "Running code-lspchecks..."
    make code-lspchecks

    echo "Running code-security..."
    make code-security

    echo "Running code-deptry..."
    make code-deptry

    echo "Running code-spell..."
    make code-spell

    echo "Running code-semgrep..."
    make code-semgrep

    echo "Running code-audit..."
    make code-audit

    echo "Running tests..."
    make test

    echo "✓ All CI checks passed"

# Run all CI validation checks (quiet mode - only show errors)
ci-quiet:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{ PROJECT_ROOT }}

    echo "=== Running CI Checks (Quiet Mode) ==="
    TMPFILE=$(mktemp)

    make init > "$TMPFILE" 2>&1 || { echo "✗ Init failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Init passed"

    make test-integration-config > "$TMPFILE" 2>&1 || { echo "✗ Test-integration-config failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Test-integration-config passed"

    make code-style > "$TMPFILE" 2>&1 || { echo "✗ Code-style failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Code-style passed"

    make code-typecheck > "$TMPFILE" 2>&1 || { echo "✗ Code-typecheck failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Code-typecheck passed"

    make code-lspchecks > "$TMPFILE" 2>&1 || { echo "✗ Code-lspchecks failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Code-lspchecks passed"

    make code-security > "$TMPFILE" 2>&1 || { echo "✗ Code-security failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Code-security passed"

    make code-deptry > "$TMPFILE" 2>&1 || { echo "✗ Code-deptry failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Code-deptry passed"

    make code-spell > "$TMPFILE" 2>&1 || { echo "✗ Code-spell failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Code-spell passed"

    make code-semgrep > "$TMPFILE" 2>&1 || { echo "✗ Code-semgrep failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Code-semgrep passed"

    make code-audit > "$TMPFILE" 2>&1 || { echo "✗ Code-audit failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Code-audit passed"

    make test > "$TMPFILE" 2>&1 || { echo "✗ Test failed"; cat "$TMPFILE"; rm "$TMPFILE"; exit 1; }
    echo "✓ Test passed"

    rm "$TMPFILE"
    echo "✓ All CI checks passed"

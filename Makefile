# X-RAG Platform - Makefile
# Main developer interface for infrastructure and application management
#
# Convention: All targets end with @echo "" for visual separation in terminal output

.PHONY: help check init cluster-init
.PHONY: cluster-start cluster-stop cluster-status cluster-clean cluster-reset cluster-destroy
.PHONY: apps-generate-grpc apps-build apps-deploy
.PHONY: test test-integration test-coverage test-e2e
.PHONY: code-style code-format code-typecheck code-security code-deptry code-stats code-spell
.PHONY: ci ci-quiet
.PHONY: logs-search-ui logs-search-service logs-embedding logs-ingest logs-indexer
.PHONY: logs-weaviate logs-kafka logs-redis
.PHONY: cli-weaviate cli-kafka cli-redis cli-minio cli-embedding cli-ingest cli-indexer
.PHONY: cli-search-ui cli-search-service cli-prometheus cli-grafana
.PHONY: open-search-ui open-ingestion-api open-weaviate open-grafana open-prometheus open-k8-dashboard
.PHONY: dashboard-token

# Configuration
CLUSTER_NAME := xrag-k8
NAMESPACE := rag-system
REGISTRY_NAME := xrag-k8-kind-registry
REGISTRY_PORT := 5000
SETUP_DIR := .setup

# Color codes for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m  # No Color

# Default target
.DEFAULT_GOAL := help

##@ General

help: ## Display this help message
	@clear
	@echo "$(BLUE)X-RAG Platform - Available Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(CYAN)<target>$(NC)\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""

##@ Prerequisites

check: ## Validate all prerequisites (Docker, kubectl, Kind, Helm, Python, uv)
	@clear
	@echo "$(BLUE)=== Checking Prerequisites ===$(NC)"
	@./scripts/check-prerequisites.sh
	@echo ""

init: ## Initialize local development environment
	@echo "$(BLUE)=== Initializing Development Environment ===$(NC)"
	@mkdir -p reports/coverage
	@mkdir -p reports/security
	@mkdir -p data/storage
	@mkdir -p .setup
	@echo "Installing Python dependencies..."
	@uv sync --all-extras
	@echo ""
	@echo "Generating gRPC code..."
	@$(MAKE) apps-generate-grpc
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo ""

##@ Cluster Management

cluster-init: init check ## Build Docker images and prepare for deployment
	@echo "$(BLUE)=== Building Docker Images ===$(NC)"
	@$(MAKE) apps-build
	@echo ""
	@echo "$(GREEN)✓ Cluster initialization complete - ready for deployment$(NC)"
	@echo ""

cluster-start: ## Start the cluster and all services
	@echo "$(BLUE)=== Starting X-RAG Platform ===$(NC)"
	@echo ""
	@mkdir -p $(SETUP_DIR)
	@$(MAKE) .setup-cluster
	@$(MAKE) .setup-registry
	@$(MAKE) .deploy-infrastructure
	@$(MAKE) .deploy-monitoring
	@$(MAKE) apps-deploy
	@echo ""
	@echo "$(GREEN)===== X-RAG Platform Started! =====$(NC)"
	@echo ""
	@echo "Endpoints:"
	@echo "  Search UI:     http://localhost:8080"
	@echo "  Ingestion API: http://localhost:8082"
	@echo "  Weaviate:      http://localhost:8081/v1/.well-known/ready"
	@echo "  Grafana:       http://localhost:3000 (admin/admin)"
	@echo "  Prometheus:    http://localhost:9090"
	@echo "  Redis:         localhost:6379"
	@echo "  Kafka:         localhost:9092"
	@echo ""

cluster-stop: ## Shutdown the cluster
	@echo "$(YELLOW)Shutting down cluster...$(NC)"
	@kind delete cluster --name $(CLUSTER_NAME) 2>/dev/null || true
	@docker rm -f $(REGISTRY_NAME) 2>/dev/null || true
	@echo "$(GREEN)Cluster stopped$(NC)"
	@echo ""

cluster-status: ## Display current system status and test all service connectivity
	@./scripts/cluster-status.sh
	@echo ""

cluster-clean: ## Delete cluster, registry, and all data
	@echo "$(YELLOW)Deleting cluster and all data...$(NC)"
	@kind delete cluster --name $(CLUSTER_NAME) 2>/dev/null || true
	@docker rm -f $(REGISTRY_NAME) 2>/dev/null || true
	@rm -rf $(SETUP_DIR)
	@rm -rf data/storage/*
	@echo "$(GREEN)Cleanup complete$(NC)"
	@echo ""

cluster-reset: ## Reset all pods and data (keeps cluster running, deletes all state)
	@echo "$(YELLOW)WARNING: Deleting all pod data and restarting services$(NC)"
	@echo "$(BLUE)=== Resetting X-RAG Platform ===$(NC)"
	@echo ""
	@echo "$(YELLOW)[1/6] Deleting all workloads...$(NC)"
	@kubectl delete deployments --all -n $(NAMESPACE) --ignore-not-found
	@kubectl delete statefulsets --all -n $(NAMESPACE) --ignore-not-found
	@kubectl delete jobs --all -n $(NAMESPACE) --ignore-not-found
	@echo "$(GREEN)✓ All workloads deleted$(NC)"
	@echo ""
	@echo "$(YELLOW)[2/6] Deleting all services and configmaps...$(NC)"
	@kubectl delete services --all -n $(NAMESPACE) --ignore-not-found
	@kubectl delete configmaps --all -n $(NAMESPACE) --ignore-not-found
	@echo "$(GREEN)✓ All services and configs deleted$(NC)"
	@echo ""
	@echo "$(YELLOW)[3/6] Deleting all persistent volume claims...$(NC)"
	@kubectl delete pvc --all -n $(NAMESPACE) --ignore-not-found
	@echo "$(GREEN)✓ All data deleted$(NC)"
	@echo ""
	@echo "$(YELLOW)[4/6] Clearing deployment checkpoints...$(NC)"
	@rm -f $(SETUP_DIR)/infrastructure.done $(SETUP_DIR)/monitoring.done
	@echo "$(GREEN)✓ Checkpoints cleared$(NC)"
	@echo ""
	@echo "$(YELLOW)[5/6] Waiting for cleanup to complete...$(NC)"
	@sleep 5
	@echo "$(GREEN)✓ Cleanup complete$(NC)"
	@echo ""
	@echo "$(YELLOW)[6/6] Redeploying all services...$(NC)"
	@$(MAKE) .deploy-infrastructure
	@$(MAKE) .deploy-monitoring
	@$(MAKE) apps-deploy
	@echo ""
	@echo "$(GREEN)===== Reset Complete! =====$(NC)"
	@echo ""
	@echo "All services have been redeployed with fresh state."
	@echo "Run 'make cluster-status' to verify all services are running."
	@echo ""

cluster-destroy: cluster-stop ## Stop cluster and delete all xrag-* Docker images
	@echo "$(RED)WARNING: This will DELETE all project Docker images!$(NC)"
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo "$(YELLOW)Deleting project Docker images...$(NC)"
	@for img in $$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "xrag-"); do \
		echo "  Deleting $$img"; \
		docker rmi -f $$img 2>/dev/null || true; \
	done
	@echo "  Deleting registry:2"; docker rmi -f registry:2 2>/dev/null || true
	@echo "  Deleting kindest/node"; docker rmi -f kindest/node 2>/dev/null || true
	@for img in $$(grep -rh "image:" infra/k8s/ | grep -v "^#" | awk '{print $$NF}' | sort -u); do \
		echo "  Deleting $$img"; \
		docker rmi -f $$img 2>/dev/null || true; \
	done
	@rm -rf $(SETUP_DIR)
	@echo "$(GREEN)All project images deleted$(NC)"
	@echo ""

##@ Application Build & Deploy

apps-generate-grpc: ## Generate Python gRPC code from protocol buffers
	@echo "$(BLUE)=== Generating gRPC Code ===$(NC)"
	@./scripts/generate-grpc.sh
	@echo ""

apps-build: ## Build all Docker images and push to local registry
	@echo "$(BLUE)=== Building Docker Images ===$(NC)"
	@./scripts/build-images.sh
	@echo ""

apps-deploy: ## Deploy application services to cluster
	@echo "$(BLUE)=== Deploying Applications ===$(NC)"
	@./scripts/deploy-apps.sh
	@echo ""

##@ Code Quality & Validation

code-style: ## Check code style and formatting (read-only)
	@echo "$(BLUE)=== Checking Code Style ===$(NC)"
	@uv run ruff check .
	@echo ""
	@uv run ruff format --check .
	@echo ""
	@echo "$(GREEN)✓ Style checks passed$(NC)"
	@echo ""

code-format: ## Auto-fix code style and formatting
	@echo "$(BLUE)=== Formatting Code ===$(NC)"
	@uv run ruff check . --fix
	@echo ""
	@uv run ruff format .
	@echo ""
	@echo "$(GREEN)✓ Code formatted$(NC)"
	@echo ""

code-typecheck: ## Run static type checking with mypy
	@echo "$(BLUE)=== Running Type Checks ===$(NC)"
	@uv run mypy src/
	@echo ""
	@echo "$(GREEN)✓ Type checks passed$(NC)"
	@echo ""

code-security: ## Run security checks with bandit
	@echo "$(BLUE)=== Running Security Checks ===$(NC)"
	@mkdir -p reports/security
	@uv run bandit -c pyproject.toml -r src -f txt -o reports/security/bandit.txt || true
	@uv run bandit -c pyproject.toml -r src
	@echo ""
	@echo "$(GREEN)✓ Security checks passed$(NC)"
	@echo ""

code-deptry: ## Check dependency hygiene with deptry
	@echo "$(BLUE)=== Checking Dependencies ===$(NC)"
	@mkdir -p reports/deptry
	@uv run deptry src
	@echo ""
	@echo "$(GREEN)✓ Dependency checks passed$(NC)"
	@echo ""

PYGOUNT_DIRS := src/ tests/ proto/ scripts/ infra/ docs/ *.md *.toml
PYGOUNT_OPTS := --suffix=py,js,html,htm,sh,yaml,yml,proto,md,txt,css,toml,log --format=summary

code-stats: ## Generate code statistics with pygount
	@echo "$(BLUE)=== Code Statistics ===$(NC)"
	@mkdir -p reports
	@uv run pygount $(PYGOUNT_DIRS) $(PYGOUNT_OPTS)
	@echo ""
	@uv run pygount $(PYGOUNT_DIRS) $(PYGOUNT_OPTS) > reports/code-stats.txt
	@echo "$(GREEN)✓ Report saved to reports/code-stats.txt$(NC)"
	@echo ""

code-spell: ## Check spelling in code and documentation
	@echo "$(BLUE)=== Checking Spelling ===$(NC)"
	@uv run codespell src tests docs scripts infra proto *.md *.toml
	@echo ""
	@echo "$(GREEN)✓ Spelling checks passed$(NC)"
	@echo ""

##@ Testing

test: ## Run unit tests only (fast, no cluster required)
	@echo "$(BLUE)=== Running Unit Tests ===$(NC)"
	@uv run pytest tests/ -v --ignore=tests/integration
	@echo ""

test-integration: ## Run integration tests (requires running cluster)
	@echo "$(BLUE)=== Running Integration Tests ===$(NC)"
	@echo "$(YELLOW)Note: Requires running cluster (make cluster-start)$(NC)"
	@uv run pytest tests/integration/ -v -s
	@echo ""

test-coverage: init ## Run unit tests with coverage report and threshold check
	@echo "$(BLUE)=== Running Unit Tests with Coverage ===$(NC)"
	@uv run pytest tests/ -v --ignore=tests/integration \
		--cov=src \
		--cov-report=html:reports/coverage/html \
		--cov-report=term \
		--cov-report=xml:reports/coverage/coverage.xml \
		--cov-fail-under=80
	@echo ""
	@echo "$(GREEN)✓ Coverage threshold met$(NC)"
	@echo "  HTML: reports/coverage/html/index.html"
	@echo ""

test-e2e: ## Run E2E tests (destructive - resets cluster and data)
	@echo "$(BLUE)=== Running E2E Tests ===$(NC)"
	@echo "$(RED)WARNING: This will reset the cluster and delete all data!$(NC)"
	@./tests/e2e/run_all.sh
	@echo ""

##@ CI/CD

ci: init code-style code-typecheck code-security code-deptry code-spell test ## Run ALL validation checks (style + types + security + deps + spelling + tests)
	@echo "$(GREEN)✓ All CI checks passed$(NC)"
	@echo ""

ci-quiet: ## Run ALL validation checks silently (only show output on errors)
	@echo "$(BLUE)=== Running CI Checks (Quiet Mode) ===$(NC)"
	@TMPFILE=$$(mktemp); \
	$(MAKE) init > $$TMPFILE 2>&1 || { echo "$(RED)✗ Init failed$(NC)"; cat $$TMPFILE; rm $$TMPFILE; exit 1; }; \
	echo "$(GREEN)✓ Init passed$(NC)"; \
	$(MAKE) code-style > $$TMPFILE 2>&1 || { echo "$(RED)✗ Code-style failed$(NC)"; cat $$TMPFILE; rm $$TMPFILE; exit 1; }; \
	echo "$(GREEN)✓ Code-style passed$(NC)"; \
	$(MAKE) code-typecheck > $$TMPFILE 2>&1 || { echo "$(RED)✗ Code-typecheck failed$(NC)"; cat $$TMPFILE; rm $$TMPFILE; exit 1; }; \
	echo "$(GREEN)✓ Code-typecheck passed$(NC)"; \
	$(MAKE) code-security > $$TMPFILE 2>&1 || { echo "$(RED)✗ Code-security failed$(NC)"; cat $$TMPFILE; rm $$TMPFILE; exit 1; }; \
	echo "$(GREEN)✓ Code-security passed$(NC)"; \
	$(MAKE) code-deptry > $$TMPFILE 2>&1 || { echo "$(RED)✗ Code-deptry failed$(NC)"; cat $$TMPFILE; rm $$TMPFILE; exit 1; }; \
	echo "$(GREEN)✓ Code-deptry passed$(NC)"; \
	$(MAKE) code-spell > $$TMPFILE 2>&1 || { echo "$(RED)✗ Code-spell failed$(NC)"; cat $$TMPFILE; rm $$TMPFILE; exit 1; }; \
	echo "$(GREEN)✓ Code-spell passed$(NC)"; \
	$(MAKE) test > $$TMPFILE 2>&1 || { echo "$(RED)✗ Test failed$(NC)"; cat $$TMPFILE; rm $$TMPFILE; exit 1; }; \
	echo "$(GREEN)✓ Test passed$(NC)"; \
	rm $$TMPFILE; \
	echo ""; \
	echo "$(GREEN)✓ All CI checks passed$(NC)"; \
	echo ""
	@echo ""

##@ Monitoring & Logs

logs-search-ui: ## Tail Search UI logs
	@kubectl logs -f -l app=search-ui -n $(NAMESPACE)
	@echo ""

logs-search-service: ## Tail Search Service logs
	@kubectl logs -f -l app=search-service -n $(NAMESPACE)
	@echo ""

logs-embedding: ## Tail Embedding Service logs
	@kubectl logs -f -l app=embedding-service -n $(NAMESPACE)
	@echo ""

logs-ingest: ## Tail Ingestion API logs
	@kubectl logs -f -l app=ingestion-api -n $(NAMESPACE)
	@echo ""

logs-indexer: ## Tail Indexer logs
	@kubectl logs -f -l app=indexer -n $(NAMESPACE)
	@echo ""

logs-weaviate: ## Tail Weaviate logs
	@kubectl logs -f -l app=weaviate -n $(NAMESPACE)
	@echo ""

logs-kafka: ## Tail Kafka logs
	@kubectl logs -f -l app=kafka -n $(NAMESPACE)
	@echo ""

logs-redis: ## Tail Redis logs
	@kubectl logs -f -l app=redis -n $(NAMESPACE)
	@echo ""

##@ Pod CLI Access

cli-weaviate: ## Connect to Weaviate pod shell
	@./scripts/connect-pod.sh xrag-weaviate $(NAMESPACE)
	@echo ""

cli-kafka: ## Connect to Kafka pod shell
	@./scripts/connect-pod.sh xrag-kafka $(NAMESPACE)
	@echo ""

cli-redis: ## Connect to Redis pod shell
	@./scripts/connect-pod.sh xrag-redis $(NAMESPACE)
	@echo ""

cli-minio: ## Connect to MinIO pod shell
	@./scripts/connect-pod.sh xrag-minio $(NAMESPACE)
	@echo ""

cli-embedding: ## Connect to Embedding Service pod shell
	@./scripts/connect-pod.sh embedding-service $(NAMESPACE)
	@echo ""

cli-ingest: ## Connect to Ingestion API pod shell
	@./scripts/connect-pod.sh ingestion-api $(NAMESPACE)
	@echo ""

cli-indexer: ## Connect to Indexer pod shell
	@./scripts/connect-pod.sh indexer $(NAMESPACE)
	@echo ""

cli-search-ui: ## Connect to Search UI pod shell
	@./scripts/connect-pod.sh search-ui $(NAMESPACE)
	@echo ""

cli-search-service: ## Connect to Search Service pod shell
	@./scripts/connect-pod.sh search-service $(NAMESPACE)
	@echo ""

cli-prometheus: ## Connect to Prometheus pod shell
	@./scripts/connect-pod.sh xrag-prometheus $(NAMESPACE)
	@echo ""

cli-grafana: ## Connect to Grafana pod shell
	@./scripts/connect-pod.sh xrag-grafana $(NAMESPACE)
	@echo ""

##@ UI Shortcuts

open-search-ui: ## Open Search UI in browser (http://localhost:8080)
	@echo "$(BLUE)=== Opening Search UI ===$(NC)"
	@echo "URL: http://localhost:8080"
	@if command -v open > /dev/null 2>&1; then \
		open http://localhost:8080; \
	elif command -v xdg-open > /dev/null 2>&1; then \
		xdg-open http://localhost:8080; \
	else \
		echo "$(YELLOW)Please open http://localhost:8080 in your browser$(NC)"; \
	fi
	@echo ""

open-ingestion-api: ## Open Ingestion API docs in browser (http://localhost:8082/docs)
	@echo "$(BLUE)=== Opening Ingestion API Documentation ===$(NC)"
	@echo "URL: http://localhost:8082/docs"
	@if command -v open > /dev/null 2>&1; then \
		open http://localhost:8082/docs; \
	elif command -v xdg-open > /dev/null 2>&1; then \
		xdg-open http://localhost:8082/docs; \
	else \
		echo "$(YELLOW)Please open http://localhost:8082/docs in your browser$(NC)"; \
	fi
	@echo ""

open-weaviate: ## Open Weaviate console in browser (http://localhost:8081)
	@echo "$(BLUE)=== Opening Weaviate Console ===$(NC)"
	@echo "URL: http://localhost:8081/v1/meta"
	@if command -v open > /dev/null 2>&1; then \
		open http://localhost:8081/v1/meta; \
	elif command -v xdg-open > /dev/null 2>&1; then \
		xdg-open http://localhost:8081/v1/meta; \
	else \
		echo "$(YELLOW)Please open http://localhost:8081/v1/meta in your browser$(NC)"; \
	fi
	@echo ""

open-grafana: ## Open Grafana dashboard in browser (http://localhost:3000)
	@echo "$(BLUE)=== Opening Grafana Dashboard ===$(NC)"
	@echo "URL: http://localhost:3000"
	@echo "Credentials: admin / admin"
	@if command -v open > /dev/null 2>&1; then \
		open http://localhost:3000; \
	elif command -v xdg-open > /dev/null 2>&1; then \
		xdg-open http://localhost:3000; \
	else \
		echo "$(YELLOW)Please open http://localhost:3000 in your browser$(NC)"; \
	fi
	@echo ""

open-prometheus: ## Open Prometheus UI in browser (http://localhost:9090)
	@echo "$(BLUE)=== Opening Prometheus UI ===$(NC)"
	@echo "URL: http://localhost:9090"
	@if command -v open > /dev/null 2>&1; then \
		open http://localhost:9090; \
	elif command -v xdg-open > /dev/null 2>&1; then \
		xdg-open http://localhost:9090; \
	else \
		echo "$(YELLOW)Please open http://localhost:9090 in your browser$(NC)"; \
	fi
	@echo ""

open-k8-dashboard: ## Open Kubernetes Dashboard in browser (https://localhost:8443)
	@echo "$(BLUE)=== Opening Kubernetes Dashboard ===$(NC)"
	@echo "Setting up port-forward..."
	@kubectl port-forward -n kubernetes-dashboard svc/kubernetes-dashboard 8443:443 > /dev/null 2>&1 & \
	echo $$! > /tmp/k8-dashboard-port-forward.pid
	@sleep 2
	@echo "$(GREEN)✓ Dashboard available at https://localhost:8443$(NC)"
	@echo ""
	@echo "$(YELLOW)Authentication Required:$(NC)"
	@echo "  1. Click 'Token' option"
	@echo "  2. Run: make show-k8-dashboard-token"
	@echo "  3. Copy the token and paste it"
	@echo "  4. Click 'Sign In'"
	@echo ""
	@echo "$(YELLOW)Note: Port-forward is running in background (PID: $$(cat /tmp/k8-dashboard-port-forward.pid))$(NC)"
	@echo "To stop: kill $$(cat /tmp/k8-dashboard-port-forward.pid)"
	@echo ""
	@if command -v open > /dev/null 2>&1; then \
		open https://localhost:8443; \
	elif command -v xdg-open > /dev/null 2>&1; then \
		xdg-open https://localhost:8443; \
	else \
		echo "$(YELLOW)Please open https://localhost:8443 in your browser$(NC)"; \
	fi
	@echo ""

show-k8-dashboard-token: ## Display Kubernetes Dashboard access token
	@./scripts/get-dashboard-token.sh
	@echo ""

# Internal targets (prefixed with . to hide from help)

.setup-cluster:
	@if [ -f $(SETUP_DIR)/cluster.done ]; then \
		echo "$(GREEN)[SKIP]$(NC) Cluster already exists"; \
	else \
		echo "$(YELLOW)[CREATE]$(NC) Setting up Kind cluster..."; \
		./scripts/create-cluster.sh; \
		touch $(SETUP_DIR)/cluster.done; \
	fi

.setup-registry:
	@if [ -f $(SETUP_DIR)/registry.done ]; then \
		echo "$(GREEN)[SKIP]$(NC) Registry already running"; \
	else \
		echo "$(YELLOW)[CREATE]$(NC) Setting up container registry..."; \
		./scripts/setup-registry.sh; \
		touch $(SETUP_DIR)/registry.done; \
	fi

.deploy-infrastructure:
	@if [ -f $(SETUP_DIR)/infrastructure.done ]; then \
		echo "$(GREEN)[SKIP]$(NC) Infrastructure already deployed"; \
	else \
		echo "$(YELLOW)[DEPLOY]$(NC) Deploying infrastructure services..."; \
		./scripts/deploy-infrastructure.sh; \
		touch $(SETUP_DIR)/infrastructure.done; \
	fi

.deploy-monitoring:
	@if [ -f $(SETUP_DIR)/monitoring.done ]; then \
		echo "$(GREEN)[SKIP]$(NC) Monitoring already deployed"; \
	else \
		echo "$(YELLOW)[DEPLOY]$(NC) Deploying monitoring stack..."; \
		./scripts/deploy-monitoring.sh; \
		touch $(SETUP_DIR)/monitoring.done; \
	fi

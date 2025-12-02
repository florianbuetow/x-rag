# X-RAG Platform - Makefile
# Main developer interface for infrastructure and application management
#
# Convention: All targets end with @echo "" for visual separation in terminal output

.PHONY: help check setup init
.PHONY: cluster-start cluster-stop cluster-status cluster-clean cluster-reset cluster-destroy
.PHONY: apps-generate-grpc apps-build apps-deploy
.PHONY: test test-integration test-coverage
.PHONY: code-style code-format
.PHONY: ci
.PHONY: logs-search-ui logs-search-service logs-embedding logs-ingest logs-indexer
.PHONY: logs-weaviate logs-kafka logs-redis

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
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(CYAN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""

##@ Prerequisites

check: ## Validate all prerequisites (Docker, kubectl, Kind, Helm, Python, uv)
	@clear
	@echo "$(BLUE)=== Checking Prerequisites ===$(NC)"
	@./scripts/check-prerequisites.sh
	@echo ""

setup: check ## Build Docker images (does not start cluster)
	@echo "$(BLUE)=== Building Docker Images ===$(NC)"
	@$(MAKE) apps-build
	@echo ""
	@echo "$(GREEN)✓ Setup complete$(NC)"
	@echo ""

init: ## Initialize project directories and dependencies
	@echo "$(BLUE)=== Initializing Project ===$(NC)"
	@mkdir -p reports/coverage
	@mkdir -p data/storage
	@mkdir -p .setup
	@echo "$(GREEN)✓ Project initialized$(NC)"
	@echo ""

##@ Cluster Management

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
	@./scripts/check-status.sh
	@echo ""

cluster-clean: ## Delete cluster, registry, and all data
	@echo "$(YELLOW)Deleting cluster and all data...$(NC)"
	@kind delete cluster --name $(CLUSTER_NAME) 2>/dev/null || true
	@docker rm -f $(REGISTRY_NAME) 2>/dev/null || true
	@rm -rf $(SETUP_DIR)
	@rm -rf data/storage/*
	@echo "$(GREEN)Cleanup complete$(NC)"
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

cluster-reset: ## Reset all pods and data (keeps cluster running, deletes all state)
	@echo "$(YELLOW)WARNING: This will DELETE all pod data and restart services!$(NC)"
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
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

test-coverage: init ## Run all tests with coverage report and threshold check
	@echo "$(BLUE)=== Running All Tests with Coverage ===$(NC)"
	@uv run pytest tests/ -v -s \
		--cov=src \
		--cov-report=html:reports/coverage/html \
		--cov-report=term \
		--cov-report=xml:reports/coverage/coverage.xml \
		--cov-fail-under=80
	@echo ""
	@echo "$(GREEN)✓ Coverage threshold met$(NC)"
	@echo "  HTML: reports/coverage/html/index.html"
	@echo ""

##@ CI/CD

ci: code-style test-coverage ## Run ALL validation checks (style + all tests with coverage)
	@echo "$(GREEN)✓ All CI checks passed$(NC)"
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

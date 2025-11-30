# X-RAG Platform - Makefile
# Main developer interface for infrastructure and application management

.PHONY: help check setup start stop status clean clean-force reset destroy
.PHONY: build deploy-apps
.PHONY: test test-e2e
.PHONY: logs-search-ui logs-search-service logs-embedding logs-ingest logs-indexer
.PHONY: logs-weaviate logs-kafka logs-redis

# Configuration
CLUSTER_NAME := rag-hackathon
NAMESPACE := rag-system
REGISTRY_NAME := kind-registry
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
	@echo "$(BLUE)X-RAG Platform - Available Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(CYAN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup & Management

check: ## Validate all prerequisites (Docker, kubectl, Kind, Helm, Python, uv)
	@echo "$(BLUE)=== Checking Prerequisites ===$(NC)"
	@./scripts/check-prerequisites.sh

setup: ## One-time setup (create cluster, deploy infrastructure)
	@echo "$(BLUE)=== X-RAG Platform - Initial Setup ===$(NC)"
	@echo ""
	@mkdir -p $(SETUP_DIR)
	@$(MAKE) check
	@$(MAKE) .setup-cluster
	@$(MAKE) .setup-registry
	@$(MAKE) .deploy-infrastructure
	@$(MAKE) .deploy-monitoring
	@echo ""
	@echo "$(GREEN)===== Setup Complete! =====$(NC)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and add your OPENAI_API_KEY"
	@echo "  2. Run: make build    # Build application images"
	@echo "  3. Run: make start    # Start all services"

start: ## Start/restart all services (builds and deploys applications)
	@echo "$(BLUE)=== Starting X-RAG Platform ===$(NC)"
	@echo ""
	@if ! kind get clusters 2>/dev/null | grep -q "$(CLUSTER_NAME)"; then \
		echo "$(RED)Error: Cluster not found. Run 'make setup' first.$(NC)"; \
		exit 1; \
	fi
	@$(MAKE) build
	@$(MAKE) deploy-apps
	@echo ""
	@echo "$(GREEN)===== X-RAG Platform Started! =====$(NC)"
	@echo ""
	@echo "Endpoints:"
	@echo "  Search UI:     http://localhost:8080"
	@echo "  Ingestion API: http://localhost:8082"
	@echo "  Weaviate:      http://localhost:8081/v1/.well-known/ready"
	@echo "  Grafana:       http://localhost:3000 (admin/admin)"
	@echo "  Prometheus:    http://localhost:9090"

stop: ## Stop all services (keeps cluster running)
	@echo "$(YELLOW)Stopping application services...$(NC)"
	@kubectl delete deployment --all -n $(NAMESPACE) 2>/dev/null || true
	@echo "$(GREEN)Services stopped. Cluster still running.$(NC)"
	@echo "To completely remove everything, run: make clean"

status: ## Display current system status
	@echo "$(BLUE)=== Cluster Status ===$(NC)"
	@kind get clusters 2>/dev/null | grep "$(CLUSTER_NAME)" || echo "Cluster not found"
	@echo ""
	@echo "$(BLUE)=== Pods ===$(NC)"
	@kubectl get pods -n $(NAMESPACE) 2>/dev/null || echo "Namespace not found"
	@echo ""
	@echo "$(BLUE)=== Services ===$(NC)"
	@kubectl get svc -n $(NAMESPACE) 2>/dev/null || echo "Namespace not found"

clean: ## Interactive cleanup with confirmation
	@echo "$(YELLOW)WARNING: This will delete the Kind cluster and all data.$(NC)"
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo "Deleting cluster..."
	@kind delete cluster --name $(CLUSTER_NAME) || true
	@echo "Stopping registry..."
	@docker rm -f $(REGISTRY_NAME) 2>/dev/null || true
	@echo "Removing checkpoints..."
	@rm -rf $(SETUP_DIR)
	@echo -n "Delete data directory? [y/N] " && read ans && [ $${ans:-N} = y ] && rm -rf data/storage/* || true
	@echo "$(GREEN)Cleanup complete$(NC)"

clean-force: ## Force cleanup without confirmation
	@echo "$(YELLOW)Force deleting cluster and data...$(NC)"
	@kind delete cluster --name $(CLUSTER_NAME) 2>/dev/null || true
	@docker rm -f $(REGISTRY_NAME) 2>/dev/null || true
	@rm -rf $(SETUP_DIR)
	@rm -rf data/storage/*
	@echo "$(GREEN)Force cleanup complete$(NC)"

destroy: stop ## Stop services and DELETE all Docker images
	@echo "$(RED)WARNING: This will DELETE all X-RAG Docker images!$(NC)"
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo "$(YELLOW)Deleting Docker images...$(NC)"
	@docker images --format "{{.Repository}}:{{.Tag}}" | grep "localhost:$(REGISTRY_PORT)" | xargs -r docker rmi -f 2>/dev/null || true
	@docker images --format "{{.Repository}}:{{.Tag}}" | grep "x-rag" | xargs -r docker rmi -f 2>/dev/null || true
	@echo "$(GREEN)Docker images deleted$(NC)"
	@echo "Cluster and infrastructure still running. Run 'make clean' to remove everything."

reset: clean setup ## Clean and recreate everything (fresh start)

##@ Build & Deploy

build: ## Build all Docker images and push to local registry
	@echo "$(BLUE)=== Building Docker Images ===$(NC)"
	@./scripts/build-images.sh

deploy-apps: ## Deploy application services to cluster
	@echo "$(BLUE)=== Deploying Applications ===$(NC)"
	@./scripts/deploy-apps.sh

##@ Testing

test: ## Run all tests using pytest
	@echo "$(BLUE)=== Running Tests ===$(NC)"
	@uv run pytest tests/ -v

test-e2e: ## Run end-to-end integration tests
	@echo "$(BLUE)=== Running E2E Tests ===$(NC)"
	@uv run pytest tests/test_e2e.py -v

##@ Monitoring & Logs

logs-search-ui: ## Tail Search UI logs
	@kubectl logs -f -l app=search-ui -n $(NAMESPACE)

logs-search-service: ## Tail Search Service logs
	@kubectl logs -f -l app=search-service -n $(NAMESPACE)

logs-embedding: ## Tail Embedding Service logs
	@kubectl logs -f -l app=embedding-service -n $(NAMESPACE)

logs-ingest: ## Tail Ingestion API logs
	@kubectl logs -f -l app=ingestion-api -n $(NAMESPACE)

logs-indexer: ## Tail Indexer logs
	@kubectl logs -f -l app=indexer -n $(NAMESPACE)

logs-weaviate: ## Tail Weaviate logs
	@kubectl logs -f -l app=weaviate -n $(NAMESPACE)

logs-kafka: ## Tail Kafka logs
	@kubectl logs -f -l app=kafka -n $(NAMESPACE)

logs-redis: ## Tail Redis logs
	@kubectl logs -f -l app=redis -n $(NAMESPACE)

##@ Internal Targets (do not call directly)

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

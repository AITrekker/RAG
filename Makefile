# Makefile for Enterprise RAG Platform

# Variables
COMPOSE_FILE = docker-compose.yml
COMPOSE_DEV = docker-compose.yml -f docker-compose.override.yml  
COMPOSE_PROD = docker-compose.yml -f docker-compose.prod.yml
BACKEND_SERVICE = backend
FRONTEND_SERVICE = frontend

# Default target
.PHONY: help
help: ## Show this help message
	@echo "🏢 Enterprise RAG Platform - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# 🚀 Main Development Commands
.PHONY: up
up: ## Start all services in development mode (auto-includes frontend container)
	docker-compose up -d

.PHONY: up-prod
up-prod: ## Start all services in production mode
	docker-compose -f $(COMPOSE_PROD) up -d

.PHONY: down
down: ## Stop all services and remove containers
	docker-compose down

.PHONY: logs
logs: ## View logs from all services
	docker-compose logs -f

.PHONY: ps
ps: ## Show running containers with health status
	docker-compose ps

# 🔨 Build Commands  
.PHONY: build
build: ## Build all containers
	docker-compose build

.PHONY: backend-build
backend-build: ## Quick backend rebuild (6+ minute build time due to ML dependencies)
	@echo "🔨 Building backend container - this takes ~6 minutes due to HuggingFace/PyTorch cache..."
	@echo "⏱️  Set timeout to 360000ms (6 minutes) if using programmatic builds"
	docker-compose build $(BACKEND_SERVICE)

.PHONY: frontend-build
frontend-build: ## Build frontend container (development)
	docker-compose build $(FRONTEND_SERVICE)

.PHONY: frontend-build-prod
frontend-build-prod: ## Build frontend container (production)
	docker-compose -f $(COMPOSE_PROD) build $(FRONTEND_SERVICE)

# 🖥️ Frontend Management
.PHONY: frontend-dev
frontend-dev: ## Start frontend in development mode with hot reload
	docker-compose up -d $(FRONTEND_SERVICE)

.PHONY: frontend-shell
frontend-shell: ## Open shell in frontend container for debugging
	docker-compose exec $(FRONTEND_SERVICE) /bin/sh

.PHONY: frontend-yarn
frontend-yarn: ## Run yarn dev manually in container (for debugging)
	docker-compose exec $(FRONTEND_SERVICE) npm run dev

.PHONY: frontend-install
frontend-install: ## Install/update frontend dependencies
	docker-compose exec $(FRONTEND_SERVICE) npm install

# ⚙️ Service Management
.PHONY: restart-backend
restart-backend: ## Restart backend service
	docker-compose restart $(BACKEND_SERVICE)

.PHONY: restart-frontend  
restart-frontend: ## Restart frontend service
	docker-compose restart $(FRONTEND_SERVICE)

# 📋 Development Helpers
.PHONY: backend-logs
backend-logs: ## View backend logs
	docker-compose logs -f $(BACKEND_SERVICE)

.PHONY: frontend-logs
frontend-logs: ## View frontend logs  
	docker-compose logs -f $(FRONTEND_SERVICE)

.PHONY: shell-backend
shell-backend: ## Open shell in backend container
	docker-compose exec $(BACKEND_SERVICE) /bin/bash

# 🗄️ Database Management
.PHONY: db-shell
db-shell: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U rag_user -d rag_db

.PHONY: db-backup
db-backup: ## Backup database
	docker-compose exec postgres pg_dump -U rag_user rag_db > backup_$(shell date +%Y%m%d_%H%M%S).sql

# 🧹 Cleanup Commands
.PHONY: clean
clean: ## Remove containers and volumes
	docker-compose down -v

.PHONY: clean-all
clean-all: ## Remove everything including images
	docker-compose down -v --rmi all

.PHONY: prune
prune: ## Remove unused Docker resources
	docker system prune -f

# 🧪 Testing Commands
.PHONY: test
test: ## Run complete test suite
	python scripts/test_system.py

.PHONY: setup-demo
setup-demo: ## Setup demo tenants with sample data
	python scripts/workflow/setup_demo_tenants.py

.PHONY: verify
verify: ## Verify system setup and health
	python scripts/verify_admin_setup.py

# 🎯 Quick Commands
.PHONY: quick-start
quick-start: build up setup-demo ## Complete setup: build, start, and setup demo data
	@echo "🎉 Enterprise RAG Platform is ready!"
	@echo "🌐 Frontend: http://localhost:3000"
	@echo "📚 API Docs: http://localhost:8000/docs" 
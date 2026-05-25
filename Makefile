.PHONY: help dev prod test clean lint logs build

.DEFAULT_GOAL := help

# Compose project name keeps dev and prod stacks distinct.
DEV_PROJECT  := moa-dev
PROD_PROJECT := moa-prod

DEV_COMPOSE  := docker compose -p $(DEV_PROJECT) --env-file dev.env
PROD_COMPOSE := docker compose -p $(PROD_PROJECT) -f docker-compose.prod.yml --env-file prod.env

## Show this help (default)
help:
	@awk 'BEGIN {printf "Usage: make <target>\n\nTargets:\n"} \
		/^## / {doc = substr($$0, 4); next} \
		/^[a-zA-Z_-]+:/ {name = $$1; sub(/:.*/, "", name); \
			if (doc) printf "  \033[36m%-8s\033[0m %s\n", name, doc; doc = ""}' \
		$(MAKEFILE_LIST)

## Start dev stack with hot-reload
dev:
	$(DEV_COMPOSE) up --build

## Start prod-optimized stack (detached)
prod:
	$(PROD_COMPOSE) up --build -d
	@echo "Moa is running. Frontend: http://localhost:5173  Backend: http://localhost:8000"

## Run backend unit tests
test:
	$(DEV_COMPOSE) run --rm --no-deps backend pytest -q

## Stop everything and prune volumes for both stacks
clean:
	-$(DEV_COMPOSE)  down -v --remove-orphans
	-$(PROD_COMPOSE) down -v --remove-orphans

## Tail logs from the dev stack
logs:
	$(DEV_COMPOSE) logs -f

## Build images without starting services
build:
	$(DEV_COMPOSE) build

## Lint backend (ruff) and frontend (eslint) inside their containers
lint:
	-$(DEV_COMPOSE) run --rm --no-deps backend  ruff check app tests
	-$(DEV_COMPOSE) run --rm --no-deps frontend npm run lint

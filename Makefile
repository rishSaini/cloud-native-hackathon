# TalkScout dev commands. Run `make help` to list them.

-include .env
export

VENV  := .venv
PY    := $(CURDIR)/$(VENV)/bin/python
BIN   := $(CURDIR)/$(VENV)/bin
IMAGE := talkscout:dev

.PHONY: help setup es-up kibana es-down ingest run test image run-image gitar-results

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Create the venv, install packages, turn on git hooks, create .env
	python3 -m venv $(VENV)
	"$(PY)" -m pip install -q -r backend/requirements-dev.txt
	git config core.hooksPath .githooks
	@test -f .env || cp .env.example .env

es-up: ## Start Elasticsearch at http://localhost:9200
	docker compose up -d --wait elasticsearch

kibana: ## Start Kibana at http://localhost:5601
	docker compose --profile kibana up -d

es-down: ## Stop Elasticsearch and Kibana (keeps the data)
	docker compose --profile kibana down

ingest: ## Load data/sample.jsonl into Elasticsearch
	"$(PY)" scripts/ingest.py data/sample.jsonl

run: ## Run the app at http://localhost:8000 (with telemetry if OTEL_EXPORTER_OTLP_ENDPOINT is set)
ifdef OTEL_EXPORTER_OTLP_ENDPOINT
	cd backend && "$(BIN)/opentelemetry-instrument" "$(BIN)/uvicorn" app.main:app --port 8000
else
	cd backend && "$(BIN)/uvicorn" app.main:app --reload --port 8000
endif

test: ## Run the backend tests
	cd backend && "$(PY)" -m pytest -q

image: ## Build the container image, as CI does
	docker build -t $(IMAGE) .

run-image: image ## Run the container image at http://localhost:8080
	docker run --rm -p 8080:8080 --env-file .env -e ES_URL=http://host.docker.internal:9200 $(IMAGE)

gitar-results: ## Export Gitar reviews into gitar/results (needs gh auth)
	"$(PY)" scripts/gitar_export.py

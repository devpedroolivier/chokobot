PYTHON ?= python3

.PHONY: install install-dev lint test check run run-edge run-conversation docker-build docker-up docker-down split-up split-down

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e .[dev]

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) scripts/run_tests.py

check: lint test

run:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-edge:
	$(PYTHON) -m uvicorn app.edge_main:app --host 0.0.0.0 --port 8004 --reload

run-conversation:
	$(PYTHON) -m uvicorn app.conversation_main:app --host 0.0.0.0 --port 8005 --reload

docker-build:
	docker build -t chokobot .

docker-up:
	docker compose up --build -d chokobot

docker-down:
	docker compose down

split-up:
	docker compose --profile split up --build -d chokobot-redis chokobot-conversation chokobot-edge

split-down:
	docker compose --profile split down

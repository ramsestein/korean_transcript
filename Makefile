.PHONY: build up down logs test test-live eval eval-live clean lint

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd backend && python -m pytest -m "unit or integration" && cd ../frontend && npm test

test-live:
	cd backend && python -m pytest -m live_api

eval:
	cd backend && python -m pytest tests/prompt_eval/test_prompt_quality.py -v

eval-live:
	cd backend && python -m pytest tests/prompt_eval --live-llm-judge -v

lint:
	cd backend && python -m ruff check app/ tests/

clean:
	docker compose down -v
	rm -rf data/*

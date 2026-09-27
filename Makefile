.PHONY: install test lint run build-data docker-build docker-run

install:
	python -m pip install -r requirements.txt
	python -m pip install -e .

test:
	pytest tests/ -v

lint:
	ruff check .

run:
	uvicorn retail_nl2sql.api:app --reload

build-data:
	python build_star_schema.py --input-dir data/raw --output data/retail_star_schema.db

docker-build:
	docker build -t retail-nl2sql .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env retail-nl2sql


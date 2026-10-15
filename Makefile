.PHONY: deps check format lint migrations migrate run test

deps:
	uv sync --extra postgres --group test

check:
	uv run python src/manage.py check

format:
	uv run ruff format src

lint:
	uv run ruff check src

migrations:
	uv run python src/manage.py makemigrations --check

migrate:
	uv run python src/manage.py migrate

run:
	uv run python src/manage.py runserver

test:
	uv run pytest -c src/pytest.ini src/tests

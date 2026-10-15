.PHONY: deps check migrations migrate run test

deps:
	uv sync --group test

check:
	uv run python src/manage.py check

migrations:
	uv run python src/manage.py makemigrations user

migrate:
	uv run python src/manage.py migrate

run:
	uv run python src/manage.py runserver

test:
	uv run pytest -c src/pytest.ini src/tests

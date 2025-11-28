PY=python3
PIP=$(PY) -m pip

.PHONY: venv deps alembic-upgrade alembic-revision build up logs test

venv:
	$(PY) -m venv .venv

deps: venv
	. .venv/bin/activate && $(PIP) install --upgrade pip && $(PIP) install -r requirements.txt

alembic-upgrade: deps
	. .venv/bin/activate && alembic upgrade head

alembic-revision: deps
	. .venv/bin/activate && alembic revision --autogenerate -m "autogen"

build:
	docker build -t auto_voter_webapp .

up:
	docker-compose up --build

logs:
	docker-compose logs -f

run:
	$(PY) -m app.api

test:
	$(PY) test_login.py
	$(PY) test_integration.py
	$(PY) test_socketio.py

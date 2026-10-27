PYTHON ?= ../../../.venv/bin/python
PORT ?= 8000

.PHONY: install test e2e check coverage run
install:
	$(PYTHON) -m pip install -r requirements-dev.txt
test:
	$(PYTHON) -m unittest tests.test_logic tests.test_api -v
e2e:
	$(PYTHON) -m unittest tests.test_e2e -v
check: test e2e
coverage:
	$(PYTHON) -m coverage run --source=app --branch -m unittest tests.test_logic tests.test_api -v
	$(PYTHON) -m coverage report -m
run:
	$(PYTHON) -m uvicorn app.api:app --host 127.0.0.1 --port $(PORT) --no-access-log

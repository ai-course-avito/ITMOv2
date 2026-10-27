PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: venv install run clean

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install flask

run:
	$(PY) app.py

clean:
	rm -rf .venv

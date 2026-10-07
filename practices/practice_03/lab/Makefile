.PHONY: install test
# Системный python3 на macOS — 3.9, поэтому ищем первый доступный интерпретатор 3.10+.
PYTHON ?= $(shell for p in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do \
	command -v $$p >/dev/null 2>&1 && $$p -c 'import sys; sys.exit(sys.version_info < (3,10))' 2>/dev/null && { echo $$p; break; }; done)
export PYTHON
install:
	@$(or $(PYTHON),python3) -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; print('Standard library only: ready (' + sys.version.split()[0] + ')')"
test: install
	$(MAKE) -C demo test

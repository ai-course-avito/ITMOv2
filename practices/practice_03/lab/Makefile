.PHONY: install test report
install:
	@python3 -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; print('Standard library only: ready')"
test: install
	$(MAKE) -C demo test

report: test
	python3 tools/update_report.py

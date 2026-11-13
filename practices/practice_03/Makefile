.PHONY: install test lint check check_pptx

install:
	@$(MAKE) -s -C lab install

test:
	@$(MAKE) -s -C lab test

lint:
	@python3 lint.py

check_pptx:
	@python3 check_pptx.py

check: install lint check_pptx test

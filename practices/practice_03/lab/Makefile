.PHONY: install test ask ask_agent
install:
	@python3 -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; print('Standard library only: ready')"
test: install
	$(MAKE) -C demo test

# Run five questions against local models built from Modelfile(s)
ask:
	python3 ask_questions.py --model itmo-chat --output results/resp.md

ask_agent:
	python3 ask_questions.py --model itmo-agent --output results/resp_agent.md

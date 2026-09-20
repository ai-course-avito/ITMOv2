.PHONY: test

EXPERIMENTS := \
	few_shot/experiment.md \
	rctf/experiment.md \
	chain_of_verification/experiment.md \
	tree_of_thoughts/experiment.md \
	rag/experiment.md \
	react/experiment.md

test:
	@test -f README.md
	@test -f prompts.md
	@test -f slides/practice_02.pptx
	@for file in $(EXPERIMENTS); do test -s "$$file" || { echo "Missing or empty: $$file"; exit 1; }; done
	@grep -q "Few-shot" prompts.md
	@grep -q "R.C.T.F." prompts.md
	@grep -q "Chain of Verification" prompts.md
	@grep -q "Tree of Thoughts" prompts.md
	@grep -q "RAG" prompts.md
	@grep -q "ReAct" prompts.md
	@echo "Practice 2 artifacts: OK"

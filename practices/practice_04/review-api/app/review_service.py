from typing import Protocol


class LLM(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class ReviewService:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def review(self, diff: str) -> dict[str, str]:
        prompt = f"Review this pull request and find problems:\n{diff}"
        answer = self.llm.generate(prompt)
        return {"comment": answer}

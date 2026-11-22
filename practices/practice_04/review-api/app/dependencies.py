from app.review_service import ReviewService


class StubLLM:
    """Детерминированная заглушка внешнего LLM: сеть и ключи не нужны."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return "stub review: no problems found"


llm = StubLLM()
review_service = ReviewService(llm)

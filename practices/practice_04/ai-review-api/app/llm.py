"""Заглушка LLM-клиента: детерминированная, без сети."""


class LLMClient:
    def review(self, diff: str) -> dict:
        files = sum(1 for line in diff.splitlines() if line.startswith("diff --git"))
        return {
            "summary": f"Файлов в diff: {files}",
            "comments": [
                {
                    "file": "unknown",
                    "line": 1,
                    "text": "Заглушка: проверьте изменения вручную.",
                }
            ],
        }


def get_llm_client() -> LLMClient:
    return LLMClient()

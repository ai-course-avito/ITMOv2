"""Клиент локальной модели из практики 3.

Собственный system передаётся в каждом запросе. На практике 3 проверено, что
request-level system полностью заменяет SYSTEM, запечённый в сборку, поэтому
поведение не зависит от того, какая сборка стоит в OLLAMA_MODEL.
"""

import json
import os
import urllib.request

DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "itmo-local:latest"
REVIEW_TIMEOUT_SECONDS = 30

OPTIONS = {
    "temperature": 0.2,
    "seed": 42,
    "num_ctx": 4096,
    "num_predict": 512,
}


class OllamaClient:
    def __init__(self, url=None, model=None):
        self.url = (url or os.environ.get("OLLAMA_URL") or DEFAULT_URL).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL") or DEFAULT_MODEL

    def complete(self, system, user):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": False,
            "options": OPTIONS,
        }
        request = urllib.request.Request(
            self.url + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=REVIEW_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["message"]["content"]

{
  "summary": "Добавлен ReviewService.review, который отправляет полный diff во внешний LLM и возвращает лишь {\"comment\"}. В API добавлен POST /api/reviews, который без валидации берет payload\"diff\" и проксирует в сервис.",
  "risks": [
    {
      "file": "app/review_service.py",
      "line": 12,
      "evidence": "prompt = f\"Review this pull request and find problems:\\n{diff}\"",
      "risk": "Сырой diff уходит во внешний LLM без редактирования секретов (SEC-1)."
    },
    {
      "file": "app/review_service.py",
      "line": 14,
      "evidence": "return {\"comment\": answer}",
      "risk": "Ответ не соответствует OUT-1: нет summary/risks/checks."
    },
    {
      "file": "app/api.py",
      "line": 9,
      "evidence": "return review_service.review(payload\"diff\")",
      "risk": "Нет проверки длины diff и возврата 413 для >20000 символов (API-1)."
    }
  ],
  "checks": 
    "OUT-1: запустить сервис и выполнить POST /api/reviews с {\"diff\":\"x\"}; убедиться, что в ответе только ключ \"comment\" и отсутствуют summary/risks/checks.",
    "API-1: выполнить POST /api/reviews с diff длиной 20001+ символов; ожидать 413 согласно правилу, зафиксировать фактический статус (ожидаемо не 413).",
    "SEC-1: в тесте замокать LLM.generate так, чтобы он возвращал полученный prompt; передать diff с строкой \"token=TEST_TOKEN\" и убедиться, что в возвращенном тексте присутствует token=TEST_TOKEN (нет редактирования)."
  
}
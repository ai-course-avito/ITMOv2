1. Краткое резюме
- В PR добавлен метод ReviewService.review, который формирует промпт из diff и вызывает LLM, возвращая словарь {"comment": answer}.
- В FastAPI-приложение добавлена POST-ручка /api/reviews, которая принимает payload: dict и обращается к review_service.review(payload["diff"]) без явной валидации и обработки ошибок.

2. Риски
1) Candidate: Отсутствует валидация тела запроса; KeyError при отсутствии поля diff приведёт к 500
   Evidence: practices/practice_01/TRAINING_PR.diff:36–37 — функция create_review(payload: dict) обращается к payload["diff"] напрямую: return review_service.review(payload["diff"]).
   Rule: Валидация обязательных полей запроса должна приводить к предсказуемой клиентской ошибке (422), а не к необработанному исключению сервера (500).

2) Candidate: Нет обработки ошибок внешнего LLM; исключение из generate вызовет 500 и утечку внутренних деталей
   Evidence: practices/practice_01/TRAINING_PR.diff:21 — answer = self.llm.generate(prompt) без try/except; practices/practice_01/TRAINING_PR.diff:35–37 — эндпойнт возвращает результат без перехвата исключений сервиса.
   Rule: Ошибки внешних зависимостей должны преобразовываться в контролируемые ответы API (например, 502/503) без утечки стек-трейса.

3) Candidate: Нестабильный контракт API — нет схем запроса/ответа (response_model), ответ формируется произвольно
   Evidence: practices/practice_01/TRAINING_PR.diff:35 — @app.post("/api/reviews") без response_model; 36 — вход типизирован как dict; 19–22 — метод review возвращает dict[str, str] без валидации.
   Rule: Публичные эндпойнты должны иметь фиксированный контракт (схемы запроса/ответа), чтобы OpenAPI и рантайм-валидация совпадали и клиенты были совместимы.

3. Воспроизводимые проверки
Подготовка (запуск сервера):
- Команда: uvicorn app.api:app --host 127.0.0.1 --port 8000

Проверка 1 (нет поля diff -> KeyError -> 500):
- Команда: curl -s -X POST http://127.0.0.1:8000/api/reviews -H 'Content-Type: application/json' -d '{}' -i
- Ожидаемо: статус 500 Internal Server Error; в логах — KeyError: 'diff'.

Проверка 2 (исключение из LLM -> 500):
- Тест (pytest) с подменой зависимости:
  Содержимое tests/test_llm_failure.py:
  ```
  from fastapi.testclient import TestClient
  from app.api import app
  from app.dependencies import review_service

  class FailingLLM:
      def generate(self, prompt: str) -> str:
          raise RuntimeError("boom")

  def test_llm_failure(monkeypatch):
      monkeypatch.setattr(review_service, "llm", FailingLLM())
      client = TestClient(app)
      resp = client.post("/api/reviews", json={"diff": "x"})
      assert resp.status_code == 500
  ```
- Команда: pytest -q
- Ожидаемо: тест воспроизводит 500 при исключении из внешней зависимости.

Проверка 3 (контракт ответа не зафиксирован в OpenAPI):
- Команда: curl -s http://127.0.0.1:8000/openapi.json | jq '.paths["/api/reviews"].post.responses["200"].content["application/json"].schema'
- Ожидаемо: схема свободная (пустая или с additionalProperties: true), отсутствует строгое описание поля comment.

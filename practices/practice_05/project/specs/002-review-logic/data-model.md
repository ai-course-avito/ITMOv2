# Data Model: логика ревью

Нормативный контракт: [CONTRACT.md v1.0](../../../CONTRACT.md). Все данные живут в памяти попытки; DB и история отсутствуют.

| Сущность | Поля / ограничения | Связи |
| --- | --- | --- |
| ReviewInput | Ровно diff: string; 1–20000 Unicode code points до trim/нормализации, не только пробелы | Вход одной ReviewAttempt |
| DiffLine | path: нормализованный путь; side: old/new; line: int>0; text: точная строка с префиксом +, - или пробелом | Индекс очищенного diff для проверки Risk |
| ModelReview | Ровно summary, risks, checks | Проходит маскирование и final validation |
| summary | Непустая после trim строка, ≤1500 code points | ModelReview |
| risks | Массив 0–3 Risk | ModelReview |
| Risk | Ровно file, line, evidence, risk; file — непустой путь из diff; line — int>0, не bool; evidence — точная цитата очищенного diff с префиксом, ≤20000 code points; risk — непустая строка ≤1000 code points | Совпадение file/line/evidence с одной DiffLine; null/RULE-only запрещены |
| checks | 1–10 непустых строк, каждая ≤500 code points | ModelReview; только рекомендации, не выполнение |
| ReviewResult | request_id: UUID; mode: demo или live; поля ModelReview | mode и request_id добавляет сервер |
| ReviewError | request_id: UUID; error: ровно code/message | Нет partial review и retryable; message безопасная русская строка |
| ReviewAttempt | request_id, duration_ms, status | Только эти три поля допустимы в журнале |
| Settings | REVIEW_MODE=demo|live (default demo); REVIEW_LLM_URL/MODEL/KEY обязательны только для live | Не сериализуются в клиентский ответ, ключ не логируется |

Переходы попытки: received → input validated → sanitized → analyzing → response parsed → response sanitized → response validated → success. Любая ошибка завершает попытку контролируемым error. До analyzing внешний adapter не вызывается. Cancellation прекращает локальное ожидание без публикации позднего результата.

Пути удаления берутся из `---`, остальных файлов — из `+++`; префиксы a/ и b/ убираются, `/dev/null` не становится именем файла. Для `-` координата старая; для `+`/контекста новая. У контекстной строки счётчики обеих сторон увеличиваются, у удаления только old, у добавления только new. Hunk заголовки задают старт; сокращённые fragments допустимы.

Текстовые поля summary/risk/checks проверяются на непустоту после trim; evidence не обрезается, потому что ведущий пробел — часть цитаты. Лимиты проверяются после маскирования итогового ответа. Несоответствие любого поля завершает всё ревью ошибкой INVALID_MODEL_OUTPUT.

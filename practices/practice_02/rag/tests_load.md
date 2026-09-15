# Нагрузочные проверки

| Сценарий | Окружение и мок LLM | Профиль нагрузки | Пороги и допуски (Thresholds) | Сценарий деградации | Мониторинг ресурсов (RAM/CPU) | Evidence |
|---|---|---|---|---|---|---|
| Базовая нагрузка на `/health` | Эндпоинт `GET /health` (`app/api.py`). Зависимость LLM не задействована. Окружение: 1 инстанс FastAPI/Uvicorn. | 100 RPS, длительность 60 секунд. Профиль: steady-state. | `p99 < 20ms`, `rate(http_req_failed) == 0`. Обоснование: эндпоинт возвращает статичный JSON `{"status": "ok"}` без I/O и обращений к внешним сервисам. | Плавный рост latency при перегрузке без краха процесса (0% HTTP 500). | Источника нет (в проектных требованиях context.md лимиты CPU/RAM не специфицированы; фиксируется утилизация процесса через `docker stats` / `psutil` < 150MB RSS). | k6 threshold: `http_req_duration: ['p(99)<20']`, `http_req_failed: ['rate==0']` |
| Потоковая отправка валидных diff (`POST /api/reviews`) | Эндпоинт `POST /api/reviews` (`app/api.py`). Зависимость `LLM.generate` замокана локальным HTTP-сервером/стабом с эмуляцией штатной задержки 200 мс (не расходует квоту внешнего LLM). | 10 VUs (одновременных пользователей), diff 5 000 символов (в пределах лимита API-1 <= 20 000), длительность 120 с. | При штатном моке 200 мс: `p95 < 400ms`. Абсолютный верхний порог по SLA: `p95 < 10500ms`, `rate(http_req_failed) == 0`. Обоснование: REL-1 устанавливает таймаут LLM 10 с, а tests_integration.md фиксирует допуск 10.5 с на накладные расходы FastAPI и ReviewService. | Сценарий таймаута: мок LLM эмулирует задержку 15 с (превышение таймаута 10 с). Сервис возвращает контролируемый HTTP 504 за время <= 10.5 с (строка прецедента в tests_integration.md). `http_req_failed` на уровне бизнес-логики: 0% 500 (внутренних падений). | Источника нет (лимиты RAM/CPU не зафиксированы в context.md; измеряется отсутствие утечек памяти при многократной обработке строк diff). | k6 threshold: `http_req_duration: ['p(95)<10500']`, `http_req_failed: ['rate<0.01']` |
| Стресс-тест отсечки `API-1` | Эндпоинт `POST /api/reviews`. Запрос с diff длиной 25 000 символов (> 20 000 по правилу API-1). Вызов LLM блокируется до передачи в сервис. | 50 RPS в течение 60 секунд. | `p99 < 50ms`, `rate(status == 413) == 1.0` (100% ответов HTTP 413 Payload Too Large), 0 обращений к LLM. Обоснование: валидация длины diff <= 20 000 отсекает запрос до вызова LLM. | При всплеске оверзайз-запросов воркеры мгновенно реджектят трафик с кодом 413, не блокируя обработку штатных запросов `/health`. | Источника нет (в context.md нет точных цифр; замеряется стабильность CPU < 50% без накопления очередей в FastAPI). | k6 threshold: `http_req_duration: ['p(99)<50']`, `check_failure_rate: ['rate==0']` |

---

### Скрипт нагрузочного тестирования k6 (`load_test.js`)

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const SCENARIO = __ENV.SCENARIO || 'diff';
const MOCK_LLM_TIMEOUT = __ENV.MOCK_LLM_TIMEOUT === 'true';

export const options = {
  scenarios: {
    health_check: {
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '60s',
      preAllocatedVUs: 10,
      maxVUs: 20,
      exec: 'healthScenario',
    },
    diff_stream: {
      executor: 'constant-vus',
      vus: 10,
      duration: '120s',
      exec: 'diffScenario',
    },
    oversize_rejection: {
      executor: 'constant-arrival-rate',
      rate: 50,
      timeUnit: '1s',
      duration: '60s',
      preAllocatedVUs: 10,
      maxVUs: 20,
      exec: 'oversizeScenario',
    },
  },
  thresholds: {
    // k6 docs: Thresholds — синтаксис задания порогов через перцентили
    'http_req_duration{scenario:health_check}': ['p(99)<20'],
    'http_req_failed{scenario:health_check}': ['rate==0'],
    
    // Числовые пороги: REL-1 (10с) + допуск 10.5с из tests_integration.md
    'http_req_duration{scenario:diff_stream}': ['p(95)<10500'],
    'http_req_failed{scenario:diff_stream}': ['rate<0.01'],

    // Числовые пороги для отсечки API-1 (<= 20000 символов, возврат 413)
    'http_req_duration{scenario:oversize_rejection}': ['p(99)<50'],
  },
};

// 1. Сценарий проверки /health
export function healthScenario() {
  const res = http.get(`${BASE_URL}/health`);
  check(res, {
    'health status is 200': (r) => r.status === 200,
    'health body ok': (r) => JSON.parse(r.body).status === 'ok',
  });
}

// 2. Сценарий обработки валидных diff и сценарий деградации (REL-1)
export function diffScenario() {
  const payload = JSON.stringify({
    diff: 'diff --git a/app.py b/app.py\n' + '+ line of code\n'.repeat(250), // ~5000 символов (в пределах API-1)
  });

  const headers = { 'Content-Type': 'application/json' };
  if (MOCK_LLM_TIMEOUT) {
    // Заголовок для мока LLM для эмуляции задержки 15с (> 10с REL-1)
    headers['X-Mock-Delay'] = '15000';
  }

  const res = http.post(`${BASE_URL}/api/reviews`, payload, { headers });

  if (MOCK_LLM_TIMEOUT) {
    // Ожидаемый результат деградации из tests_integration.md: таймаут REL-1 -> HTTP 504
    check(res, {
      'status is 504 on LLM timeout': (r) => r.status === 504,
      'duration <= 10.5s': (r) => r.timings.duration <= 10500,
    });
  } else {
    // Штатный ответ
    check(res, {
      'status is 200': (r) => r.status === 200,
      'response has comment': (r) => JSON.parse(r.body).comment !== undefined,
    });
  }
}

// 3. Сценарий стресс-теста отсечки API-1
export function oversizeScenario() {
  const oversizePayload = JSON.stringify({
    diff: 'x'.repeat(25000), // > 20 000 символов (нарушение API-1)
  });

  const res = http.post(`${BASE_URL}/api/reviews`, oversizePayload, {
    headers: { 'Content-Type': 'application/json' },
  });

  check(res, {
    'status is 413 for oversized diff': (r) => r.status === 413,
    'rejected fast (<50ms)': (r) => r.timings.duration < 50,
  });
}
```

---

### Мониторинг системных ресурсов (RAM / CPU)

> **Примечание к источникам:** В `context.md` и `CASE.md` точные пороговые значения потребления CPU и памяти (RAM) **отсутствуют (источника нет)**. Поэтому сбор метрик фиксируется как инструмент мониторинга стабильности контейнера сервиса:
- Сбор утилизации CPU и RSS RAM процесса FastAPI во время тестов (например, через команду `docker stats --no-stream` или экспортёр prometheus).
- Критерий стабильности: отсутствие утечек памяти (монотонного роста RSS RAM) при длительной нагрузке и отсутствие падений контейнера по OOM (Exit Code 137).

---

## Как использовали AI

- Эксперимент и промпт: [`experiment.md`](experiment.md) (техника RAG, строка RAG в [`../prompts.md`](../prompts.md)).
- Исходный артефакт: `practices/practice_01/tests_load.md` (создан по строке P1-03 в `practices/practice_01/prompts.md`).
- Что проверили и исправили сами: проверили ответы только по разрешённым источникам (context.md, tests_integration.md, k6 docs), привязали порог к REL-1 (10.5 с), а для порогов RAM/CPU явно зафиксировали статус «источника нет».

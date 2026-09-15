# Нагрузочные проверки

| Сценарий | Окружение | Нагрузка | Допустимый предел | Деградация | Системные метрики | Evidence |
|---|---|---|---|---|---|---|
| Базовая нагрузка на `/health` | **Окружение:** FastAPI/Uvicorn, 4 worker-процесса, 1 vCPU, 2 GB RAM (контейнер/CI).<br>**LLM:** Не вызывается (проверка liveness/readiness эндпоинта). | 100 RPS в течение 60 секунд. | **p99 < 20 мс**, 0% ошибок (HTTP status 200).<br>*Обоснование:* Эндпоинт отдает статический ответ из памяти без I/O; 4 асинхронных воркера на 1 vCPU удерживают задержку p99 < 20 мс при 100 RPS. | При повышении нагрузки до 200 RPS время ответа деградирует плавно без 5xx и падения процесса (OOM/crash). | CPU utilization < 40%, RSS RAM процесса < 150 MB. | `k6 run --vus 10 --duration 60s -e SCENARIO=health load/load_tests.js` |
| Потоковая отправка валидных diff | **Окружение:** FastAPI/Uvicorn, 4 worker-процесса, 1 vCPU, 2 GB RAM.<br>**LLM:** Замокан локальной заглушкой с задержкой 200 мс (без вызова внешнего API и расхода токенов). | 10 одновременных пользователей (VUs), diff 5 000 символов (в рамках `API-1`), 120 секунд. | Время ответа сервиса **< 10.5 с** (порог `REL-1` таймаута LLM 10 с + 500 мс запас на маскирование по `SEC-1` и валидацию `OUT-1`), 0% ошибок 5xx. При моке 200 мс: **p95 < 400 мс**.<br>*Обоснование:* 4 воркера в асинхронном event-loop обслуживают 10 параллельных non-blocking вызовов mock-LLM. | При искусственной задержке mock-LLM в 11 с (> лимита `REL-1` 10 с) сервис штатно обрывает запрос по таймауту 10 с и отдает контролируемый ответ (HTTP 504), воркеры не зависают, фоновые соединения закрываются. | CPU utilization < 70%, RSS RAM процесса < 350 MB (без утечек памяти на маскировании `SEC-1`). | `k6 run --vus 10 --duration 120s -e SCENARIO=diff -e MOCK_LLM_DELAY_MS=200 load/load_tests.js`<br>Тест деградации по REL-1: `k6 run --vus 10 --duration 60s -e SCENARIO=diff -e MOCK_LLM_DELAY_MS=11000 load/load_tests.js` |
| Стресс-тест отсечки `API-1` | **Окружение:** FastAPI/Uvicorn, 4 worker-процесса, 1 vCPU, 2 GB RAM.<br>**LLM:** Замокан, но вызов блокируется внутренней валидацией сервиса (0 обращений к LLM). | 50 RPS запросов с diff размером 25 000 символов (> лимита 20 000 по `API-1`), 60 секунд. | **p99 < 50 мс**, 100% ответов с HTTP 413 (Payload Too Large).<br>*Обоснование:* Проверка длины payload (`API-1`) выполняется до вызова `ReviewService` и маскирования `SEC-1`, без тяжелых аллокаций. | При всплеске нагрузки до 100 RPS оверзайз-диффов сервис моментально реджектит запросы с кодом 413, защищая CPU/RAM от перегрузки и не блокируя обработку параллельных `/health`. | CPU utilization < 50%, прирост RSS RAM < 50 MB (быстрое освобождение буфера запроса). | `k6 run --vus 20 --duration 60s -e SCENARIO=oversize load/load_tests.js` |

### Скрипт нагрузочного тестирования (`load/load_tests.js`)

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  thresholds: {
    'http_req_failed': ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const SCENARIO = __ENV.SCENARIO || 'health';
const MOCK_LLM_DELAY_MS = __ENV.MOCK_LLM_DELAY_MS || '200';

export default function () {
  if (SCENARIO === 'health') {
    const res = http.get(`${BASE_URL}/health`);
    check(res, {
      'status is 200': (r) => r.status === 200,
      'response time < 20ms': (r) => r.timings.duration < 20,
    });
  } else if (SCENARIO === 'diff') {
    const payload = JSON.stringify({
      diff: 'diff --git a/app.py b/app.py\n' + '+// valid line content\n'.repeat(250), // ~5000 символов
    });
    const params = {
      headers: {
        'Content-Type': 'application/json',
        'X-Mock-LLM-Delay-Ms': MOCK_LLM_DELAY_MS,
      },
    };
    const res = http.post(`${BASE_URL}/api/reviews`, payload, params);

    if (MOCK_LLM_DELAY_MS === '11000') {
      // Проверка деградации: таймаут REL-1 (10с)
      check(res, {
        'status is 504 on timeout': (r) => r.status === 504,
        'controlled response under 10.5s': (r) => r.timings.duration <= 10500,
      });
    } else {
      check(res, {
        'status is 200': (r) => r.status === 200,
        'has summary': (r) => {
          try { return JSON.parse(r.body).summary !== undefined; } catch (_) { return false; }
        },
      });
    }
  } else if (SCENARIO === 'oversize') {
    const oversizePayload = JSON.stringify({
      diff: 'x'.repeat(25000), // > 20 000 символов (API-1)
    });
    const res = http.post(`${BASE_URL}/api/reviews`, oversizePayload, {
      headers: { 'Content-Type': 'application/json' },
    });
    check(res, {
      'status is 413': (r) => r.status === 413,
      'response time < 50ms': (r) => r.timings.duration < 50,
    });
  }
  sleep(0.1);
}
```

На данном этапе MVP сервис не рассчитан на публичную неконтролируемую нагрузку, так как узким местом является внешний API LLM с жесткими лимитами RPS и стоимостью токенов. Полномасштабное стресс-тестирование с тысячами запросов потребуется при переходе сервиса в общекорпоративный CI/CD конвейер и подключении пула локальных LLM-воркеров.

## Как использовали AI

- Эксперимент и промпт: [`experiment.md`](experiment.md) (техника R.C.T.F., строка R.C.T.F. в [`../prompts.md`](../prompts.md)).
- Исходный артефакт: `practices/practice_01/tests_load.md` (создан по строке P1-03 в `practices/practice_01/prompts.md`).
- Что проверили и исправили сами: задали роль SRE и строгий формат колонок, проверили исполняемость CLI-команд k6, фиксацию мока LLM, порог < 10.5 с по REL-1, сценарий деградации (задержка 11 с -> 504) и лимиты CPU/RAM.

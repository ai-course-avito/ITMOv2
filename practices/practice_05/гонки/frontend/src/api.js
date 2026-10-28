// Клиент API таблицы рекордов (specs/contract.md §2.4–2.5).
// Функции не бросают исключений: всегда возвращают { ok: true, data } или
// { ok: false, kind }, где kind — "retryable" (можно «Повторить»),
// "rejected" (сервер отклонил данные, повтор не поможет) или "aborted"
// (запрос отменён самим экраном, например «Новой игрой»).

export const API_BASE = "http://localhost:8000";
export const REQUEST_TIMEOUT_MS = 5000;

async function request(path, init, signal) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onExternalAbort);
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
    if (!response.ok) {
      // 4xx — данные отклонены (422, 413 …); 5xx (в т. ч. 503) — сервер/хранилище
      return { ok: false, kind: response.status < 500 ? "rejected" : "retryable" };
    }
    return { ok: true, data: await response.json() };
  } catch {
    if (signal?.aborted && !timedOut) return { ok: false, kind: "aborted" };
    // сеть, таймаут, невалидный JSON в ответе
    return { ok: false, kind: "retryable" };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onExternalAbort);
  }
}

export function getLeaderboard({ signal } = {}) {
  return request("/leaderboard", { method: "GET" }, signal);
}

export function saveRaceResult({ name, lapTimeMs }, { signal } = {}) {
  return request(
    "/race-results",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, lap_time_ms: lapTimeMs }),
    },
    signal,
  );
}

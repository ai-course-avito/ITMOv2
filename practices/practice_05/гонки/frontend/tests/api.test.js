import { test, beforeEach, afterEach, mock } from "node:test";
import assert from "node:assert/strict";

import { getLeaderboard, saveRaceResult, REQUEST_TIMEOUT_MS } from "../src/api.js";

const realFetch = globalThis.fetch;

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// fetch, который никогда не отвечает сам, но честно реагирует на abort
function hangingFetch(_url, init) {
  return new Promise((_resolve, reject) => {
    init.signal.addEventListener("abort", () => {
      reject(new DOMException("aborted", "AbortError"));
    });
  });
}

beforeEach(() => {
  globalThis.fetch = realFetch;
});

afterEach(() => {
  globalThis.fetch = realFetch;
  mock.timers.reset();
});

test("200 с таблицей → ok и данные как в ответе", async () => {
  const board = { entries: [], total: 0, last_result: null };
  globalThis.fetch = async () => jsonResponse(200, board);
  assert.deepEqual(await getLeaderboard(), { ok: true, data: board });
});

test("GET /leaderboard без параметра limit", async () => {
  let calledUrl = null;
  globalThis.fetch = async (url) => {
    calledUrl = url;
    return jsonResponse(200, { entries: [], total: 0, last_result: null });
  };
  await getLeaderboard();
  assert.equal(calledUrl, "http://localhost:8000/leaderboard");
});

test("fetch отклонён (сервер выключен) → retryable", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  assert.deepEqual(await getLeaderboard(), { ok: false, kind: "retryable" });
});

test("нет ответа за 5000 мс → retryable", async () => {
  mock.timers.enable({ apis: ["setTimeout"] });
  globalThis.fetch = hangingFetch;
  const pending = getLeaderboard();
  mock.timers.tick(REQUEST_TIMEOUT_MS);
  assert.equal(REQUEST_TIMEOUT_MS, 5000);
  assert.deepEqual(await pending, { ok: false, kind: "retryable" });
});

test("503 → retryable", async () => {
  globalThis.fetch = async () =>
    jsonResponse(503, { detail: "Хранилище рекордов недоступно" });
  assert.deepEqual(await saveRaceResult({ name: "Камила", lapTimeMs: 65400 }), {
    ok: false,
    kind: "retryable",
  });
});

test("422 и 413 → rejected", async () => {
  for (const status of [422, 413]) {
    globalThis.fetch = async () => jsonResponse(status, { detail: "x" });
    assert.deepEqual(await saveRaceResult({ name: "Камила", lapTimeMs: 65400 }), {
      ok: false,
      kind: "rejected",
    });
  }
});

test("внешний signal отменён («Новая игра») → aborted", async () => {
  globalThis.fetch = hangingFetch;
  const controller = new AbortController();
  const pending = saveRaceResult({ name: "Камила", lapTimeMs: 65400 }, { signal: controller.signal });
  controller.abort();
  assert.deepEqual(await pending, { ok: false, kind: "aborted" });
});

test("POST /race-results — тело ровно {name, lap_time_ms}", async () => {
  let call = null;
  globalThis.fetch = async (url, init) => {
    call = { url, init };
    return jsonResponse(201, {
      name: "Камила",
      lap_time_ms: 65400,
      best_time_ms: 65400,
      is_new_record: true,
      place: 1,
    });
  };
  const result = await saveRaceResult({ name: "Камила", lapTimeMs: 65400 });
  assert.equal(call.url, "http://localhost:8000/race-results");
  assert.equal(call.init.method, "POST");
  assert.equal(call.init.headers["Content-Type"], "application/json");
  assert.equal(call.init.body, '{"name":"Камила","lap_time_ms":65400}');
  assert.equal(result.ok, true);
  assert.equal(result.data.place, 1);
});

test("2xx с невалидным JSON → retryable", async () => {
  globalThis.fetch = async () => new Response("<html>", { status: 200 });
  assert.deepEqual(await getLeaderboard(), { ok: false, kind: "retryable" });
});

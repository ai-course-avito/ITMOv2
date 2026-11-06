import test from "node:test";
import assert from "node:assert/strict";

import {
  REQUEST_TIMEOUT_MS,
  USER_TEXT,
  canSubmit,
  createReviewer,
  interpretResponse,
  userText,
  viewState,
} from "./app.js";

const STATS = { files: 1, added: 1, removed: 1 };
const json = (body) => JSON.stringify(body);

function response(status, body) {
  return { status, text: async () => (typeof body === "string" ? body : json(body)) };
}

test("canSubmit: пустой и пробельный ввод нельзя отправить", () => {
  assert.equal(canSubmit(""), false);
  assert.equal(canSubmit("  \n\t "), false);
  assert.equal(canSubmit("+print(1)"), true);
});

test("тайм-аут страницы по контракту — 45 секунд", () => {
  assert.equal(REQUEST_TIMEOUT_MS, 45000);
});

test("ok: ревью и статистика, без сообщения", () => {
  const outcome = interpretResponse(200, json({ status: "ok", review: "нет замечаний", stats: STATS }));
  assert.equal(outcome.kind, "ok");
  assert.equal(outcome.review, "нет замечаний");
  assert.deepEqual(outcome.stats, STATS);
  assert.deepEqual(viewState(outcome), {
    showReview: true,
    showStats: true,
    message: null,
    details: null,
  });
});

test("rejected/empty_diff и diff_too_large: текст отказа, без ревью и статистики", () => {
  for (const code of ["empty_diff", "diff_too_large"]) {
    const outcome = interpretResponse(400, json({ status: "rejected", code, message: "dev text" }));
    assert.equal(outcome.kind, "rejected");
    const view = viewState(outcome);
    assert.equal(view.showReview, false);
    assert.equal(view.showStats, false);
    assert.equal(view.message, USER_TEXT[code]);
  }
});

test("request_too_large показывается тем же текстом, что diff_too_large", () => {
  const outcome = interpretResponse(
    413,
    json({ status: "request_error", code: "request_too_large", message: "тело больше 1048576 байт" }),
  );
  assert.equal(outcome.kind, "request_error");
  assert.equal(userText(outcome), USER_TEXT.diff_too_large);
  assert.equal(viewState(outcome).showStats, false);
});

test("error: текст по коду и статистика, message сервера — только в подробностях", () => {
  const message = "не удалось установить соединение с моделью: [Errno 111] Connection refused";
  const outcome = interpretResponse(
    502,
    json({ status: "error", code: "model_unavailable", message, stats: STATS }),
  );
  assert.equal(outcome.kind, "model_error");
  const view = viewState(outcome);
  assert.equal(view.showReview, false);
  assert.equal(view.showStats, true);
  assert.equal(view.message, USER_TEXT.model_unavailable);
  assert.ok(!view.message.includes("Errno"));
  assert.ok(view.details.includes(message));
});

test("каждый код model_* даёт свой непустой текст", () => {
  for (const code of ["model_timeout", "model_unavailable", "model_http_error", "model_bad_response"]) {
    const outcome = interpretResponse(502, json({ status: "error", code, message: "x", stats: STATS }));
    assert.ok(userText(outcome), code);
  }
});

test("решает status в теле, а не HTTP-код", () => {
  assert.equal(interpretResponse(502, json({ status: "ok", review: "r", stats: STATS })).kind, "ok");
  assert.equal(interpretResponse(200, json({ status: "error", code: "model_timeout", stats: STATS })).kind, "model_error");
});

test("прочие request_error — обобщённая ошибка сервиса без статистики", () => {
  for (const code of ["invalid_request", "method_not_allowed", "not_found"]) {
    const outcome = interpretResponse(400, json({ status: "request_error", code, message: "m" }));
    assert.equal(userText(outcome), USER_TEXT.network);
    assert.equal(viewState(outcome).showStats, false);
  }
});

test("тело не JSON или незнакомый status — ошибка сети/сервера", () => {
  for (const [status, body] of [
    [500, "<html>Internal Server Error</html>"],
    [200, json({ status: "maybe" })],
    [200, json(["ok"])],
    [200, "null"],
  ]) {
    const outcome = interpretResponse(status, body);
    assert.equal(outcome.kind, "network", body);
    assert.equal(userText(outcome), USER_TEXT.network);
    assert.equal(viewState(outcome).showStats, false);
  }
});

test("контроллер отправляет POST /api/review с JSON-телом", async () => {
  const calls = [];
  const reviewer = createReviewer({
    fetchImpl: async (url, init) => {
      calls.push([url, init]);
      return response(200, { status: "ok", review: "r", stats: STATS });
    },
  });
  const outcome = await reviewer.review("+x");
  assert.equal(outcome.kind, "ok");
  assert.equal(calls.length, 1);
  const [url, init] = calls[0];
  assert.equal(url, "/api/review");
  assert.equal(init.method, "POST");
  assert.equal(init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(init.body), { diff: "+x" });
});

test("пустой дифф не уходит на сервер", async () => {
  let called = 0;
  const reviewer = createReviewer({ fetchImpl: async () => { called += 1; } });
  const outcome = await reviewer.review("   ");
  assert.equal(outcome.kind, "rejected");
  assert.equal(outcome.code, "empty_diff");
  assert.equal(called, 0);
});

test("второй запрос во время первого не создаётся", async () => {
  let called = 0;
  let finish;
  const reviewer = createReviewer({
    fetchImpl: () => {
      called += 1;
      return new Promise((resolve) => { finish = resolve; });
    },
  });
  const first = reviewer.review("+x");
  assert.equal(reviewer.review("+y"), null);
  assert.equal(called, 1);
  finish(response(200, { status: "ok", review: "r", stats: STATS }));
  assert.equal((await first).kind, "ok");
  assert.notEqual(reviewer.review("+z"), null);
});

test("сбой fetch — ошибка сети/сервера", async () => {
  const reviewer = createReviewer({ fetchImpl: async () => { throw new TypeError("Failed to fetch"); } });
  const outcome = await reviewer.review("+x");
  assert.equal(outcome.kind, "network");
});

test("тайм-аут: исход network, поздний ответ игнорируется", async () => {
  let lateResolve;
  let signal;
  const reviewer = createReviewer({
    timeoutMs: 20,
    fetchImpl: (url, init) => {
      signal = init.signal;
      return new Promise((resolve, reject) => {
        lateResolve = resolve;
        init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
    },
  });
  const outcome = await reviewer.review("+x");
  assert.equal(outcome.kind, "network");
  assert.equal(signal.aborted, true);
  lateResolve(response(200, { status: "ok", review: "поздно", stats: STATS }));
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(outcome.kind, "network");
  assert.notEqual(reviewer.review("+x"), null);
});

test("тайм-аут срабатывает, даже если fetch не реагирует на abort", { timeout: 1000 }, async () => {
  let lateResolve;
  const reviewer = createReviewer({
    timeoutMs: 20,
    fetchImpl: () => new Promise((resolve) => { lateResolve = resolve; }),
  });
  const outcome = await reviewer.review("+x");
  assert.equal(outcome.kind, "network");
  lateResolve(response(200, { status: "ok", review: "поздно", stats: STATS }));
});

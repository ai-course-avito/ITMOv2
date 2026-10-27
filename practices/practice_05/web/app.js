// Страница ревью диффа review-mini.
// Контракт стыка: specs/contract/review-api.md. Файл — ES-модуль: чистые
// функции экспортируются для node --test, привязка к DOM выполняется только
// в браузере (контракт даёт один скрипт — /app.js).

export const REQUEST_TIMEOUT_MS = 45000;
const REVIEW_URL = "/api/review";
const KNOWN_STATUS = { ok: "ok", rejected: "rejected", error: "model_error", request_error: "request_error" };

export const USER_TEXT = {
  empty_diff: "Дифф пустой — вставьте текст изменений.",
  diff_too_large: "Дифф слишком большой: допустимо до 8192 байт. Сократите его и повторите.",
  model_timeout: "Модель не ответила вовремя. Статистика посчитана, ревью можно запросить ещё раз.",
  model_unavailable: "Модель сейчас недоступна. Статистика посчитана, попробуйте позже.",
  model_http_error: "Модель вернула ошибку. Статистика посчитана, попробуйте ещё раз.",
  model_bad_response: "Модель вернула ошибку. Статистика посчитана, попробуйте ещё раз.",
  network: "Не удалось получить ответ сервиса. Проверьте, что он запущен, и повторите.",
};
USER_TEXT.request_too_large = USER_TEXT.diff_too_large;

export function canSubmit(text) {
  return text.trim() !== "";
}

function networkOutcome(reason) {
  return { kind: "network", code: null, review: null, stats: null, details: reason };
}

// Контракт п.5: решает status в теле; HTTP-код — только для «подробнее».
export function interpretResponse(httpStatus, bodyText) {
  let body;
  try {
    body = JSON.parse(bodyText);
  } catch {
    return networkOutcome(`HTTP ${httpStatus}: ответ не JSON`);
  }
  const kind = body && typeof body === "object" && !Array.isArray(body) ? KNOWN_STATUS[body.status] : undefined;
  if (!kind) {
    return networkOutcome(`HTTP ${httpStatus}: незнакомый ответ`);
  }
  return {
    kind,
    code: body.code ?? null,
    review: kind === "ok" ? body.review : null,
    stats: kind === "ok" || kind === "model_error" ? body.stats ?? null : null,
    details: body.message ? `HTTP ${httpStatus}, ${body.code}: ${body.message}` : null,
  };
}

// Контракт п.6–7: текст выбирается по code, message сервера не показывается.
export function userText(outcome) {
  switch (outcome.kind) {
    case "ok":
      return null;
    case "rejected":
      return USER_TEXT[outcome.code] ?? USER_TEXT.diff_too_large;
    case "model_error":
      return USER_TEXT[outcome.code] ?? USER_TEXT.model_http_error;
    case "request_error":
      return outcome.code === "request_too_large" ? USER_TEXT.request_too_large : USER_TEXT.network;
    default:
      return USER_TEXT.network;
  }
}

export function viewState(outcome) {
  return {
    showReview: outcome.kind === "ok",
    showStats: (outcome.kind === "ok" || outcome.kind === "model_error") && outcome.stats !== null,
    message: userText(outcome),
    details: outcome.details,
  };
}

// Один запрос за раз; тайм-аут — AbortController и гонка с таймером,
// поэтому поздний ответ не меняет уже выставленный исход.
export function createReviewer({ fetchImpl, timeoutMs = REQUEST_TIMEOUT_MS }) {
  let inFlight = false;

  async function send(diff) {
    const controller = new AbortController();
    let timer;
    const timeout = new Promise((resolve) => {
      timer = setTimeout(() => {
        controller.abort();
        resolve(networkOutcome(`нет ответа за ${timeoutMs / 1000} с`));
      }, timeoutMs);
    });
    const request = (async () => {
      try {
        const response = await fetchImpl(REVIEW_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ diff }),
          signal: controller.signal,
        });
        return interpretResponse(response.status, await response.text());
      } catch (error) {
        return networkOutcome(`запрос не выполнен: ${error.message}`);
      }
    })();
    try {
      return await Promise.race([request, timeout]);
    } finally {
      clearTimeout(timer);
      inFlight = false;
    }
  }

  return {
    review(diff) {
      if (inFlight) {
        return null;
      }
      if (!canSubmit(diff)) {
        return Promise.resolve({ kind: "rejected", code: "empty_diff", review: null, stats: null, details: null });
      }
      inFlight = true;
      return send(diff);
    },
  };
}

function init(doc) {
  const input = doc.getElementById("diff");
  const button = doc.getElementById("submit");
  const loading = doc.getElementById("loading");
  const message = doc.getElementById("message");
  const result = doc.getElementById("result");
  const review = doc.getElementById("review");
  const stats = doc.getElementById("stats");
  const details = doc.getElementById("details");
  const detailsText = doc.getElementById("details-text");
  const reviewer = createReviewer({ fetchImpl: (url, options) => fetch(url, options) });
  let busy = false;

  function refreshButton() {
    button.disabled = busy || !canSubmit(input.value);
  }

  function render(outcome) {
    const view = viewState(outcome);
    result.hidden = !(view.showReview || view.showStats);
    review.hidden = !view.showReview;
    review.textContent = view.showReview ? outcome.review : "";
    stats.hidden = !view.showStats;
    if (view.showStats) {
      doc.getElementById("stat-files").textContent = outcome.stats.files;
      doc.getElementById("stat-added").textContent = outcome.stats.added;
      doc.getElementById("stat-removed").textContent = outcome.stats.removed;
    }
    message.hidden = view.message === null;
    message.textContent = view.message ?? "";
    message.dataset.kind = outcome.kind;
    details.hidden = !view.details;
    detailsText.textContent = view.details ?? "";
  }

  function clearMessage() {
    message.hidden = true;
    details.hidden = true;
  }

  input.addEventListener("input", () => {
    clearMessage();
    refreshButton();
  });

  button.addEventListener("click", async () => {
    const pending = reviewer.review(input.value);
    if (pending === null) {
      return;
    }
    busy = true;
    refreshButton();
    clearMessage();
    loading.hidden = false;
    try {
      render(await pending);
    } finally {
      busy = false;
      loading.hidden = true;
      refreshButton();
    }
  });

  refreshButton();
}

if (typeof document !== "undefined") {
  init(document);
}

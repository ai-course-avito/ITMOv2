"use strict";

(() => {
  const LIMIT = 20000;
  const WAIT_MS = 15000;
  const form = document.getElementById("review-form");
  const input = document.getElementById("diff");
  const submit = document.getElementById("submit-review");
  const clear = document.getElementById("clear-review");
  const count = document.getElementById("character-count");
  const status = document.getElementById("status");
  const error = document.getElementById("error");
  const result = document.getElementById("result");
  const summary = document.getElementById("summary");
  const risks = document.getElementById("risks");
  const checks = document.getElementById("checks");
  const mode = document.getElementById("mode");
  const riskCount = document.getElementById("risk-count");
  const noRisks = document.getElementById("no-risks");
  const requestId = document.getElementById("request-id");
  const baseDescription = "diff-help character-count privacy-note";
  let state = "idle";
  let attemptNumber = 0;
  let attempt = null;

  const messages = Object.freeze({
    UNSUPPORTED_MEDIA_TYPE: "Не удалось отправить запрос в ожидаемом формате. Повторите попытку.",
    INVALID_JSON: "Не удалось отправить запрос в ожидаемом формате. Повторите попытку.",
    INVALID_REQUEST: "Проверьте ввод: нужен непустой diff одного PR.",
    DIFF_TOO_LARGE: "Diff превышает лимит 20 000 символов. Сократите его и повторите.",
    INVALID_DIFF: "Вставьте текстовый unified diff с изменёнными строками.",
    UNSUPPORTED_DIFF: "Этот вид diff не поддерживается. Используйте обычный текстовый unified diff.",
    MODEL_NOT_CONFIGURED: "Модель не настроена на сервере. Обратитесь к владельцу локального сервиса.",
    MODEL_TIMEOUT: "Модель не ответила вовремя. Повторите попытку позже.",
    MODEL_UNAVAILABLE: "Анализ сейчас недоступен. Повторите попытку позже.",
    INVALID_MODEL_OUTPUT: "Получен некорректный результат. Повторите попытку.",
    INTERNAL_ERROR: "Не удалось выполнить анализ. Повторите попытку или сообщите идентификатор запроса.",
    NETWORK_ERROR: "Не удалось связаться с сервисом. Проверьте подключение и повторите.",
    CLIENT_TIMEOUT: "Время ожидания истекло. Повторите попытку позже."
  });

  function length(value) {
    return Array.from(value).length;
  }

  function record(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function text(value, maximum = Infinity) {
    return typeof value === "string" && value.trim().length > 0 && length(value) <= maximum;
  }

  function validResult(value) {
    if (!record(value) || !text(value.request_id) || !["live", "demo"].includes(value.mode)) return false;
    if (!text(value.summary, 1500) || !Array.isArray(value.risks) || value.risks.length > 3) return false;
    if (!Array.isArray(value.checks) || value.checks.length < 1 || value.checks.length > 10) return false;
    if (!value.checks.every(item => text(item, 500))) return false;
    return value.risks.every(item => {
      if (!record(item)) return false;
      const keys = Object.keys(item).sort();
      if (keys.join(",") !== "evidence,file,line,risk") return false;
      return text(item.file) && Number.isInteger(item.line) && item.line > 0
        && typeof item.evidence === "string" && item.evidence.length > 0
        && length(item.evidence) <= LIMIT && ["+", "-", " "].includes(item.evidence[0])
        && text(item.risk, 1000);
    });
  }

  function updateCount() {
    const size = length(input.value);
    count.textContent = `${size.toLocaleString("ru-RU")} / 20 000`;
    count.classList.toggle("over-limit", size > LIMIT);
  }

  function discardResult() {
    result.hidden = true;
    summary.textContent = "";
    risks.replaceChildren();
    checks.replaceChildren();
    mode.textContent = "";
    riskCount.textContent = "";
    requestId.textContent = "";
    noRisks.hidden = true;
  }

  function discardError() {
    error.hidden = true;
    error.replaceChildren();
    input.removeAttribute("aria-invalid");
    input.setAttribute("aria-describedby", baseDescription);
  }

  function setState(next) {
    state = next;
    document.body.dataset.state = next;
    const loading = next === "loading";
    input.disabled = loading;
    submit.disabled = loading;
    clear.disabled = loading;
    form.setAttribute("aria-busy", String(loading));
    const labels = {
      idle: "Готово к проверке.",
      loading: "Анализируем diff…",
      success: "Анализ завершён. Рекомендация доступна ниже.",
      error: "Анализ не завершён."
    };
    status.textContent = labels[next];
  }

  function appendText(parent, tag, value, className = "") {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    parent.append(element);
    return element;
  }

  function showError(message, id = "", inputError = false) {
    discardResult();
    discardError();
    setState("error");
    error.hidden = false;
    appendText(error, "p", message);
    if (text(id)) appendText(error, "p", `Запрос: ${id}`, "request-id");
    if (inputError) {
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", `${baseDescription} error`);
    }
  }

  function render(value) {
    summary.textContent = value.summary;
    riskCount.textContent = String(value.risks.length);
    riskCount.setAttribute("aria-label", `Количество возможных рисков: ${value.risks.length}`);
    mode.textContent = value.mode === "demo" ? "ДЕМО — воспроизводимая подмена модели" : "Реальный анализ";
    mode.dataset.mode = value.mode;
    noRisks.hidden = value.risks.length !== 0;
    risks.replaceChildren();
    for (const risk of value.risks) {
      const item = document.createElement("li");
      item.className = "risk-card";
      const side = risk.evidence[0] === "-" ? "старая версия" : "новая версия";
      appendText(item, "p", `${risk.file}:${risk.line} · ${side}`, "risk-location");
      appendText(item, "p", risk.risk, "preserve-lines");
      appendText(item, "p", "Цитата из diff", "evidence-label");
      appendText(item, "pre", risk.evidence, "evidence");
      risks.append(item);
    }
    checks.replaceChildren();
    value.checks.forEach(check => appendText(checks, "li", check, "preserve-lines"));
    requestId.textContent = `Запрос: ${value.request_id}`;
    result.hidden = false;
    setState("success");
  }

  function isActive(current) {
    return current.active && attempt === current && current.number === attemptNumber;
  }

  function finish(current) {
    if (!isActive(current)) return false;
    current.active = false;
    clearTimeout(current.timer);
    attempt = null;
    return true;
  }

  function serverError(body) {
    const code = record(body) && record(body.error) ? body.error.code : null;
    const message = typeof code === "string" && Object.prototype.hasOwnProperty.call(messages, code)
      && !["NETWORK_ERROR", "CLIENT_TIMEOUT"].includes(code)
      ? messages[code] : messages.INTERNAL_ERROR;
    const id = record(body) && text(body.request_id) ? body.request_id : "";
    const inputError = ["INVALID_REQUEST", "DIFF_TOO_LARGE", "INVALID_DIFF", "UNSUPPORTED_DIFF"].includes(code);
    showError(message, id, inputError);
  }

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (state === "loading") return;
    discardResult();
    discardError();
    const diff = input.value;
    if (length(diff) > LIMIT || diff.trim().length === 0) {
      showError(length(diff) > LIMIT ? messages.DIFF_TOO_LARGE : "Вставьте diff одного PR", "", true);
      input.focus();
      return;
    }

    const current = { number: ++attemptNumber, active: true, controller: new AbortController(), timer: null };
    attempt = current;
    setState("loading");
    current.timer = setTimeout(() => {
      if (!finish(current)) return;
      current.controller.abort();
      showError(messages.CLIENT_TIMEOUT);
    }, WAIT_MS);

    try {
      const response = await fetch("/api/reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ diff }),
        signal: current.controller.signal,
        cache: "no-store"
      });
      if (!isActive(current)) return;
      let body;
      try {
        body = await response.json();
      } catch {
        if (!finish(current)) return;
        showError(response.ok ? messages.INVALID_MODEL_OUTPUT : messages.INTERNAL_ERROR);
        return;
      }
      if (!isActive(current)) return;
      if (!response.ok) {
        finish(current);
        serverError(body);
      } else if (response.status !== 200 || !validResult(body)) {
        finish(current);
        showError(messages.INVALID_MODEL_OUTPUT);
      } else {
        finish(current);
        render(body);
      }
    } catch {
      if (!finish(current)) return;
      showError(messages.NETWORK_ERROR);
    }
  });

  input.addEventListener("input", () => {
    if (state === "loading") return;
    updateCount();
    discardResult();
    discardError();
    setState("idle");
  });

  clear.addEventListener("click", () => {
    if (state === "loading") return;
    input.value = "";
    updateCount();
    discardResult();
    discardError();
    setState("idle");
    input.focus();
  });

  // A fresh page starts a fresh session, including browser-restored form values.
  input.value = "";
  updateCount();
  setState("idle");
})();

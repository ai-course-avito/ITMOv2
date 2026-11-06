// Чистые функции таблицы рекордов: имя, время, таблица, победитель.
// Без Vue — проверяются `npm test` (node --test). Правила — specs/contract.md.

export const MAX_NAME_LENGTH = 20;
export const MIN_LAP_MS = 3000;
export const MAX_LAP_MS = 5999999;

// --- Имя игрока (контракт §2.1) ---

// Длина в кодовых точках Unicode: эмодзи — один символ, как на сервере.
export function nameLength(name) {
  return Array.from(name).length;
}

export function clampName(name, max = MAX_NAME_LENGTH) {
  return Array.from(name).slice(0, max).join("");
}

// Края обрезаются, любая серия пробельных символов внутри — один пробел.
export function normalizeName(name) {
  return name.trim().replace(/\s+/g, " ");
}

// Ключ сравнения: регистр не учитывается («Камила» и «камила» — один игрок).
// Эквивалент casefold() сервера: lower → upper → lower сводит «ß»/«SS», «ς»/«σ»,
// «ﬁ»/«fi» к одному виду. Отдельно — «ı» (U+0131): casefold её не меняет, а
// toUpperCase превратил бы в «I», поэтому её участки не трогаем.
export function nameKey(name) {
  return normalizeName(name)
    .split("ı")
    .map((part) => part.toLowerCase().toUpperCase().toLowerCase())
    .join("ı");
}

// null — имя в порядке, "empty" — пустое, "duplicate" — совпадает со вторым игроком.
export function validateNames(name1, name2) {
  const errors = {
    p1: normalizeName(name1) === "" ? "empty" : null,
    p2: normalizeName(name2) === "" ? "empty" : null,
  };
  if (!errors.p1 && !errors.p2 && nameKey(name1) === nameKey(name2)) {
    errors.p1 = "duplicate";
    errors.p2 = "duplicate";
  }
  return errors;
}

// --- Время (контракт §2.2) ---

// ММ:СС.сс, сотые отбрасываются (не округляются), максимум — 99:59.99.
export function formatTime(ms) {
  const clamped = Math.min(Math.max(ms, 0), MAX_LAP_MS);
  const pad = (n) => String(n).padStart(2, "0");
  const minutes = Math.floor(clamped / 60000);
  const seconds = Math.floor(clamped / 1000) % 60;
  const hundredths = Math.floor(clamped / 10) % 100;
  return `${pad(minutes)}:${pad(seconds)}.${pad(hundredths)}`;
}

export function isLapTimeSavable(ms) {
  return Number.isInteger(ms) && ms >= MIN_LAP_MS && ms <= MAX_LAP_MS;
}

// Финиш обеих машинок в одном кадре — победитель случайно 50/50 (контракт В3).
// random передаётся снаружи, чтобы тесты были детерминированными.
export function pickWinner(candidates, random) {
  if (candidates.length === 1) return candidates[0];
  return random() < 0.5 ? candidates[0] : candidates[1];
}

// --- Таблица рекордов (контракт §2.3) ---

// Строка «Последняя гонка» видна, только если её игрока нет среди показанных строк.
export function showLastResultRow(board) {
  return !!board && board.last_result != null && board.last_result.place > board.entries.length;
}

// Ключ имени игрока последней гонки, если он в топе — его строка подсвечивается.
export function highlightKey(board) {
  if (!board?.last_result) return null;
  const key = nameKey(board.last_result.name);
  return board.entries.some((entry) => nameKey(entry.name) === key) ? key : null;
}

// status — "loading" | "error" | "ready" (ответ получен)
export function leaderboardState(board, status) {
  if (status !== "ready") return status;
  return board.entries.length === 0 ? "empty" : "data";
}

import { test } from "node:test";
import assert from "node:assert/strict";

import * as logic from "../src/raceLogic.js";

// --- US1: имя игрока ---

test("nameLength считает кодовые точки: 20 эмодзи — это 20 (US1-6)", () => {
  assert.equal(logic.nameLength("🚗".repeat(20)), 20);
  assert.equal(logic.nameLength("Камила"), 6);
});

test("clampName обрезает до 20 кодовых точек (US1-6)", () => {
  assert.equal(logic.clampName("🚗".repeat(25)), "🚗".repeat(20));
  assert.equal(logic.clampName("Камила"), "Камила");
});

test("normalizeName убирает края и схлопывает пробельные серии (US1-8)", () => {
  assert.equal(logic.normalizeName("  Камила   Салис  "), "Камила Салис");
  assert.equal(logic.normalizeName("Камила\t\nСалис"), "Камила Салис");
});

test("normalizeName не трогает любые символы (US1-9)", () => {
  assert.equal(logic.normalizeName("Гонщик 🏎️ №1"), "Гонщик 🏎️ №1");
});

test("nameKey не учитывает регистр и пробелы по краям (US1-7)", () => {
  assert.equal(logic.nameKey("Камила"), logic.nameKey(" камила "));
  assert.equal(logic.nameKey("КАМИЛА"), logic.nameKey("Камила"));
});

test("validateNames: пустое имя и имя из пробелов (US1-5)", () => {
  assert.deepEqual(logic.validateNames("", "Игрок 2"), { p1: "empty", p2: null });
  assert.deepEqual(logic.validateNames("Игрок 1", "   "), { p1: null, p2: "empty" });
});

test("validateNames: одинаковые имена у обоих (US1-7)", () => {
  assert.deepEqual(logic.validateNames("Камила", " камила "), {
    p1: "duplicate",
    p2: "duplicate",
  });
});

test("validateNames: имена по умолчанию допустимы (US1-3)", () => {
  assert.deepEqual(logic.validateNames("Игрок 1", "Игрок 2"), { p1: null, p2: null });
});

// --- US2: таймер ---

test("formatTime: старт и обычное время (US2-2, US2-3)", () => {
  assert.equal(logic.formatTime(0), "00:00.00");
  assert.equal(logic.formatTime(65400), "01:05.40");
});

test("formatTime отбрасывает сотые, а не округляет (US2-3a)", () => {
  assert.equal(logic.formatTime(12346), "00:12.34");
  assert.equal(logic.formatTime(999), "00:00.99");
});

test("formatTime упирается в 99:59.99 (US2-6)", () => {
  assert.equal(logic.formatTime(5999999), "99:59.99");
  assert.equal(logic.formatTime(7000000), "99:59.99");
});

test("isLapTimeSavable: диапазон 3000–5 999 999 мс (US2-6)", () => {
  assert.equal(logic.isLapTimeSavable(2999), false);
  assert.equal(logic.isLapTimeSavable(3000), true);
  assert.equal(logic.isLapTimeSavable(5999999), true);
  assert.equal(logic.isLapTimeSavable(6000000), false);
});

test("pickWinner: один финишировавший — он и победил (US2-7)", () => {
  assert.equal(logic.pickWinner([1], () => 0.99), 1);
  assert.equal(logic.pickWinner([2], () => 0), 2);
});

test("pickWinner: финиш в одном кадре — случайно 50/50 (US2-7)", () => {
  assert.equal(logic.pickWinner([1, 2], () => 0.1), 1);
  assert.equal(logic.pickWinner([1, 2], () => 0.9), 2);
});

// --- US3: таблица рекордов ---

function makeBoard(count, lastResult) {
  const entries = Array.from({ length: count }, (_, i) => ({
    place: i + 1,
    name: `Бот ${i + 1}`,
    best_time_ms: 40000 + i * 1000,
    achieved_at: "2026-10-28T10:00:00Z",
  }));
  return { entries, total: count, last_result: lastResult };
}

test("showLastResultRow: игрок последней гонки вне топ-10 — строка есть (US3-10)", () => {
  const board = makeBoard(10, { name: "Камила", lap_time_ms: 58730, place: 13, finished_at: "x" });
  assert.equal(logic.showLastResultRow(board), true);
});

test("showLastResultRow: игрок в топ-10 — строки нет (US3-11)", () => {
  const board = makeBoard(10, { name: "Бот 4", lap_time_ms: 43000, place: 4, finished_at: "x" });
  assert.equal(logic.showLastResultRow(board), false);
});

test("showLastResultRow: гонок не было — строки нет (US3-12)", () => {
  assert.equal(logic.showLastResultRow(makeBoard(0, null)), false);
  assert.equal(logic.showLastResultRow(null), false);
});

test("highlightKey: имя последней гонки в топ-10, регистр не важен (US3-11, US3-15)", () => {
  const board = makeBoard(10, { name: "БОТ 4", lap_time_ms: 43000, place: 4, finished_at: "x" });
  assert.equal(logic.highlightKey(board), logic.nameKey("Бот 4"));
});

test("highlightKey: имени нет в топ-10 или гонок не было — null", () => {
  const board = makeBoard(10, { name: "Камила", lap_time_ms: 58730, place: 13, finished_at: "x" });
  assert.equal(logic.highlightKey(board), null);
  assert.equal(logic.highlightKey(makeBoard(3, null)), null);
});

test("leaderboardState: загрузка, ошибка, пусто, данные (US3-1, US3-4, US3-5)", () => {
  assert.equal(logic.leaderboardState(null, "loading"), "loading");
  assert.equal(logic.leaderboardState(makeBoard(3, null), "error"), "error");
  assert.equal(logic.leaderboardState(makeBoard(0, null), "ready"), "empty");
  assert.equal(logic.leaderboardState(makeBoard(3, null), "ready"), "data");
});

test("nameKey: регистр не учитывается для обычных букв — кириллица и латиница", () => {
  assert.equal(logic.nameKey("Камила Салис"), logic.nameKey("КАМИЛА салис"));
  assert.equal(logic.nameKey("Kamila"), logic.nameKey("kAMILA"));
  assert.deepEqual(logic.validateNames("Kamila", "KAMILA"), { p1: "duplicate", p2: "duplicate" });
});

test("nameKey совпадает с casefold сервера в особых случаях (контракт §2.1)", () => {
  assert.equal(logic.nameKey("Straße"), logic.nameKey("STRASSE"));
  assert.equal(logic.nameKey("ΟΔΟΣ"), logic.nameKey("οδοσ"));
  assert.equal(logic.nameKey("ﬁle"), logic.nameKey("FILE"));
  assert.notEqual(logic.nameKey("ı"), logic.nameKey("i")); // casefold различает ı и i
  assert.deepEqual(logic.validateNames("Straße", "STRASSE"), { p1: "duplicate", p2: "duplicate" });
});

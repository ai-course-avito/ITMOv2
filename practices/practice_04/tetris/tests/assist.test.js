// Фича B — помощь игроку: призрачная фигура (B1) и hold (B2).
import test from "node:test";
import assert from "node:assert/strict";
import {
  createGame,
  spawnPiece,
  ghostPiece,
  hold,
  hardDrop,
  tick,
} from "../src/game.js";

// Состояние игры с заданной активной фигурой и занятыми клетками [x, y].
function stateWith(active, filled = [], extra = {}) {
  const state = createGame(1);
  const board = state.board.map((row) => [...row]);
  for (const [x, y] of filled) board[y][x] = "Z";
  return { ...state, ...extra, board, active };
}

// ---------- B1: призрачная фигура ----------

test("B1: на пустом поле призрак T лежит на дне под фигурой", () => {
  // T в точке появления занимает строки 0–1; на дне — строки 18–19.
  const state = stateWith(spawnPiece("T"));
  assert.deepEqual(ghostPiece(state), { type: "T", rotation: 0, x: 3, y: 18 });
});

test("B1: призрак останавливается над занятой клеткой", () => {
  // O в столбцах 4–5; клетка (5, 12) занята → нижний ряд O — строка 11, y = 10.
  const state = stateWith({ type: "O", rotation: 0, x: 4, y: 0 }, [[5, 12]]);
  assert.deepEqual(ghostPiece(state), { type: "O", rotation: 0, x: 4, y: 10 });
});

test("B1: вертикальная I над колодцем — призрак на дне колодца", () => {
  // Строки 10–19 заняты везде, кроме столбца 5; I (поворот 1, x = 3) стоит в столбце 5
  // и занимает строки y…y+3 → на дне y = 16.
  const filled = [];
  for (let y = 10; y < 20; y++) {
    for (let x = 0; x < 10; x++) if (x !== 5) filled.push([x, y]);
  }
  const state = stateWith({ type: "I", rotation: 1, x: 3, y: 0 }, filled);
  assert.deepEqual(ghostPiece(state), { type: "I", rotation: 1, x: 3, y: 16 });
});

test("B1: у фигуры, лежащей на дне, призрак совпадает с ней", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 0, y: 18 });
  assert.deepEqual(ghostPiece(state), { type: "O", rotation: 0, x: 0, y: 18 });
});

test("B1: призрак не меняет состояние игры", () => {
  const state = stateWith(spawnPiece("L"), [[0, 19]]);
  const before = structuredClone(state);
  ghostPiece(state);
  assert.deepEqual(state, before);
});

// ---------- B2: hold ----------

test("B2: первый hold откладывает текущую фигуру и выводит следующую", () => {
  const state = stateWith({ type: "T", rotation: 1, x: 5, y: 7 }, [], { next: "O" });
  const after = hold(state);
  assert.equal(after.hold, "T");
  assert.deepEqual(after.active, { type: "O", rotation: 0, x: 4, y: 0 });
});

test("B2: первый hold берёт новую следующую фигуру из той же очереди seed", () => {
  // Seed 9 даёт очередь Z, L, T (сверено отдельной реализацией mulberry32 + тасовки):
  // играем Z, следующая L; после hold выходит L, следующей становится T.
  const after = hold(createGame(9));
  assert.equal(after.hold, "Z");
  assert.equal(after.active.type, "L");
  assert.equal(after.next, "T");
});

test("B2: если отложенная уже есть, hold меняет её местами с текущей", () => {
  const state = stateWith({ type: "L", rotation: 2, x: 6, y: 10 }, [], { hold: "I", next: "O" });
  const after = hold(state);
  assert.equal(after.hold, "L");
  // Отложенная выходит в точку появления в исходном повороте; очередь не сдвигается.
  assert.deepEqual(after.active, { type: "I", rotation: 0, x: 3, y: 0 });
  assert.equal(after.next, "O");
});

test("B2: второй hold до фиксации фигуры ничего не меняет", () => {
  const once = hold(stateWith(spawnPiece("T"), [], { next: "O" }));
  assert.deepEqual(hold(once), once);
});

test("B2: после фиксации фигуры hold снова доступен", () => {
  // stateWith берёт createGame(1): очередь seed 1 — O, J, L…, в мешке после старта первая L.
  // Отложили T (вышла O, следующей стала L), сбросили O — играем L;
  // следующий hold откладывает L и возвращает T в игру.
  const once = hold(stateWith(spawnPiece("T"), [], { next: "O" }));
  const locked = hardDrop(once);
  const again = hold(locked);
  assert.deepEqual(again.active, { type: "T", rotation: 0, x: 3, y: 0 });
  assert.equal(again.hold, "L");
});

test("B2: фиксация шагом падения тоже снова разрешает hold", () => {
  // Отложенная I; O лежит на дне и фиксируется следующим шагом.
  const used = stateWith({ type: "O", rotation: 0, x: 0, y: 18 }, [], {
    hold: "I",
    holdUsed: true,
    next: "T",
  });
  const again = hold(tick(used));
  assert.equal(again.hold, "T");
  assert.deepEqual(again.active, { type: "I", rotation: 0, x: 3, y: 0 });
});

test("B2: после конца игры hold ничего не меняет", () => {
  const over = stateWith(spawnPiece("T"), [], { next: "O", over: true });
  assert.deepEqual(hold(over), over);
});

test("B2: если отложенной фигуре некуда выйти, hold отменяется", () => {
  // I появляется в клетках (3..6, 1); клетка (6, 1) занята. T стоит ниже и свободна.
  const state = stateWith({ type: "T", rotation: 0, x: 0, y: 10 }, [[6, 1]], {
    hold: "I",
    next: "O",
  });
  assert.deepEqual(hold(state), state);
});

test("B2: если следующей фигуре некуда выйти, первый hold отменяется", () => {
  // O появляется в клетках (4..5, 0..1); клетка (5, 0) занята.
  const state = stateWith({ type: "T", rotation: 0, x: 0, y: 10 }, [[5, 0]], { next: "O" });
  assert.deepEqual(hold(state), state);
});

test("B2: новая игра начинается без отложенной фигуры, hold доступен", () => {
  const state = createGame(4);
  assert.equal(state.hold, null);
  assert.equal(state.holdUsed, false);
});

import test from "node:test";
import assert from "node:assert/strict";
import {
  createGame,
  pieceSequence,
  spawnPiece,
  pieceCells,
  moveLeft,
  moveRight,
  rotate,
  softDrop,
  hardDrop,
  tick,
  lineClearPoints,
  levelForLines,
  dropInterval,
} from "../src/game.js";

// Состояние игры с заданной активной фигурой и занятыми клетками [x, y].
function stateWith(active, filled = [], extra = {}) {
  const state = createGame(1);
  const board = state.board.map((row) => [...row]);
  for (const [x, y] of filled) board[y][x] = "Z";
  return { ...state, ...extra, board, active };
}

// ---------- A1: поле, фигуры, мешок из 7 ----------

test("A1: новое поле — 20 строк по 10 пустых клеток", () => {
  const { board } = createGame(1);
  assert.equal(board.length, 20);
  for (const row of board) {
    assert.deepEqual(row, [null, null, null, null, null, null, null, null, null, null]);
  }
});

test("A1: каждые 7 фигур подряд содержат все семь фигур по одному разу", () => {
  const seq = pieceSequence(42, 21);
  assert.equal(seq.length, 21);
  for (let start = 0; start < 21; start += 7) {
    const bag = seq.slice(start, start + 7).sort();
    assert.deepEqual(bag, ["I", "J", "L", "O", "S", "T", "Z"]);
  }
});

test("A1: одинаковый seed даёт одинаковую последовательность", () => {
  assert.deepEqual(pieceSequence(7, 14), pieceSequence(7, 14));
});

test("A1: разные seed дают разные последовательности", () => {
  assert.notDeepEqual(pieceSequence(1, 14), pieceSequence(2, 14));
});

test("A1: игра начинается с первых двух фигур последовательности seed", () => {
  const [first, second] = pieceSequence(5, 2);
  const state = createGame(5);
  assert.equal(state.active.type, first);
  assert.equal(state.next, second);
});

test("A1: семь фигур появляются в своих клетках", () => {
  const expected = {
    I: [[3, 1], [4, 1], [5, 1], [6, 1]],
    O: [[4, 0], [5, 0], [4, 1], [5, 1]],
    T: [[4, 0], [3, 1], [4, 1], [5, 1]],
    S: [[4, 0], [5, 0], [3, 1], [4, 1]],
    Z: [[3, 0], [4, 0], [4, 1], [5, 1]],
    J: [[3, 0], [3, 1], [4, 1], [5, 1]],
    L: [[5, 0], [3, 1], [4, 1], [5, 1]],
  };
  for (const [type, cells] of Object.entries(expected)) {
    assert.deepEqual(pieceCells(spawnPiece(type)), cells, `фигура ${type}`);
  }
});

// ---------- A2: сдвиги, поворот, wall kick ----------

test("A2: сдвиг вправо на свободное место смещает фигуру на клетку", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 4, y: 5 });
  assert.deepEqual(moveRight(state).active, { type: "O", rotation: 0, x: 5, y: 5 });
});

test("A2: сдвиг влево на свободное место смещает фигуру на клетку", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 4, y: 5 });
  assert.deepEqual(moveLeft(state).active, { type: "O", rotation: 0, x: 3, y: 5 });
});

test("A2: сдвиг влево у левой стены не выводит фигуру за поле", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 0, y: 5 });
  assert.equal(moveLeft(state).active.x, 0);
});

test("A2: сдвиг вправо у правой стены не выводит фигуру за поле", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 8, y: 5 });
  assert.equal(moveRight(state).active.x, 8);
});

test("A2: сдвиг влево не накладывает фигуру на занятую клетку", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 4, y: 5 }, [[3, 5]]);
  assert.equal(moveLeft(state).active.x, 4);
});

test("A2: поворот T по часовой разворачивает выступ вправо", () => {
  const rotated = rotate(stateWith(spawnPiece("T")));
  assert.equal(rotated.active.rotation, 1);
  assert.deepEqual(pieceCells(rotated.active), [[4, 0], [4, 1], [5, 1], [4, 2]]);
});

test("A2: четыре поворота возвращают фигуру в исходное положение", () => {
  let state = stateWith({ type: "L", rotation: 0, x: 3, y: 5 });
  for (let i = 0; i < 4; i++) state = rotate(state);
  assert.deepEqual(state.active, { type: "L", rotation: 0, x: 3, y: 5 });
});

test("A2: поворот у левой стены сдвигает фигуру на +1 (wall kick)", () => {
  // T «выступом вправо» прижата к левой стене: клетки в столбцах 0 и 1.
  const state = stateWith({ type: "T", rotation: 1, x: -1, y: 5 });
  assert.deepEqual(rotate(state).active, { type: "T", rotation: 2, x: 0, y: 5 });
});

test("A2: при занятом месте поворот сначала пробует сдвиг −1, а не +1", () => {
  // На месте мешает клетка (4, 7); подошли бы и −1, и +1 — выбирается −1.
  const state = stateWith({ type: "T", rotation: 0, x: 3, y: 5 }, [[4, 7]]);
  assert.deepEqual(rotate(state).active, { type: "T", rotation: 1, x: 2, y: 5 });
});

test("A2: вертикальная I у левой стены поворачивается со сдвигом +2", () => {
  // I в столбце 0; горизонталь не влезает при сдвигах 0, −1, +1, −2.
  const state = stateWith({ type: "I", rotation: 1, x: -2, y: 5 });
  assert.deepEqual(rotate(state).active, { type: "I", rotation: 2, x: 0, y: 5 });
});

test("A2: если ни один сдвиг не подходит, поворот отменяется", () => {
  // Колодец шириной в клетку: строки 10–19 заняты везде, кроме столбца 5.
  const filled = [];
  for (let y = 10; y < 20; y++) {
    for (let x = 0; x < 10; x++) if (x !== 5) filled.push([x, y]);
  }
  const state = stateWith({ type: "I", rotation: 1, x: 3, y: 14 }, filled);
  assert.deepEqual(rotate(state).active, { type: "I", rotation: 1, x: 3, y: 14 });
});

// ---------- A3: мягкий спуск и жёсткий сброс ----------

test("A3: новая игра начинается со счёта 0", () => {
  assert.equal(createGame(3).score, 0);
});

test("A3: мягкий спуск опускает фигуру на клетку и даёт 1 очко", () => {
  const dropped = softDrop(stateWith(spawnPiece("T")));
  assert.equal(dropped.active.y, 1);
  assert.equal(dropped.score, 1);
});

test("A3: мягкий спуск фигуры, лежащей на дне, очков не даёт", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 0, y: 18 }, [], { score: 40 });
  assert.equal(softDrop(state).score, 40);
});

test("A3: жёсткий сброс даёт 2 очка за каждую пройденную клетку", () => {
  // T из точки появления (нижняя клетка в строке 1) падает до строки 19: 18 клеток.
  const state = stateWith(spawnPiece("T"), [], { score: 5 });
  assert.equal(hardDrop(state).score, 5 + 36);
});

test("A3: жёсткий сброс сразу фиксирует фигуру на дне", () => {
  const state = stateWith(spawnPiece("T"), [], { next: "O" });
  const after = hardDrop(state);
  assert.deepEqual(after.board[18], [null, null, null, null, "T", null, null, null, null, null]);
  assert.deepEqual(after.board[19], [null, null, null, "T", "T", "T", null, null, null, null]);
  assert.deepEqual(after.active, { type: "O", rotation: 0, x: 4, y: 0 });
});

// ---------- A4: фиксация, удаление строк, очки ----------

const EMPTY_ROW = [null, null, null, null, null, null, null, null, null, null];

// Клетки строки y, кроме перечисленных столбцов.
function rowExcept(y, holes) {
  const cells = [];
  for (let x = 0; x < 10; x++) if (!holes.includes(x)) cells.push([x, y]);
  return cells;
}

test("A4: шаг падения опускает свободную фигуру на клетку без очков", () => {
  const after = tick(stateWith(spawnPiece("T")));
  assert.equal(after.active.y, 1);
  assert.equal(after.score, 0);
});

test("A4: фигура, которая не может опуститься со дна, фиксируется в поле", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 0, y: 18 }, [], { next: "T" });
  const after = tick(state);
  assert.deepEqual(after.board[18].slice(0, 3), ["O", "O", null]);
  assert.deepEqual(after.board[19].slice(0, 3), ["O", "O", null]);
  assert.deepEqual(after.active, { type: "T", rotation: 0, x: 3, y: 0 });
});

test("A4: фигура фиксируется, упёршись в занятую клетку", () => {
  const state = stateWith({ type: "O", rotation: 0, x: 0, y: 5 }, [[0, 7]]);
  const after = tick(state);
  assert.deepEqual(after.board[5].slice(0, 3), ["O", "O", null]);
  assert.deepEqual(after.board[6].slice(0, 3), ["O", "O", null]);
});

test("A4: после фиксаций очередь продолжает последовательность seed", () => {
  const seq = pieceSequence(9, 4);
  const once = hardDrop(createGame(9));
  assert.equal(once.active.type, seq[1]);
  assert.equal(once.next, seq[2]);
  const twice = hardDrop(once);
  assert.equal(twice.active.type, seq[2]);
  assert.equal(twice.next, seq[3]);
});

test("A4: заполненная строка удаляется, строки сверху сдвигаются вниз", () => {
  // Строка 19 занята, кроме столбцов 3–6; маркеры в (0, 18) и (9, 17).
  const filled = [...rowExcept(19, [3, 4, 5, 6]), [0, 18], [9, 17]];
  const state = stateWith({ type: "I", rotation: 0, x: 3, y: 18 }, filled);
  const after = tick(state);
  assert.deepEqual(after.board[19], ["Z", null, null, null, null, null, null, null, null, null]);
  assert.deepEqual(after.board[18], [null, null, null, null, null, null, null, null, null, "Z"]);
  assert.deepEqual(after.board[17], EMPTY_ROW);
  assert.deepEqual(after.board[0], EMPTY_ROW);
});

test("A4: очки за 0/1/2/3/4 строки — 0/100/300/500/800 × уровень", () => {
  const cases = [
    [0, 1, 0],
    [1, 1, 100],
    [2, 1, 300],
    [3, 1, 500],
    [4, 1, 800],
    [2, 2, 600],
    [4, 3, 2400],
  ];
  for (const [lines, level, want] of cases) {
    assert.equal(lineClearPoints(lines, level), want, `${lines} строк на уровне ${level}`);
  }
});

test("A4: две строки за раз на уровне 2 дают 600 очков", () => {
  const filled = [...rowExcept(18, [4, 5]), ...rowExcept(19, [4, 5])];
  const state = stateWith({ type: "O", rotation: 0, x: 4, y: 18 }, filled, {
    level: 2,
    lines: 10,
  });
  const after = tick(state);
  assert.equal(after.score, 600);
  assert.deepEqual(after.board[19], EMPTY_ROW);
});

test("A4: удалённые строки прибавляются к счётчику строк", () => {
  const filled = rowExcept(19, [3, 4, 5, 6]);
  const state = stateWith({ type: "I", rotation: 0, x: 3, y: 18 }, filled, { lines: 3 });
  assert.equal(tick(state).lines, 4);
});

// ---------- A5: уровень и скорость ----------

test("A5: уровень = 1 + ⌊строки / 10⌋", () => {
  const cases = [
    [0, 1],
    [9, 1],
    [10, 2],
    [19, 2],
    [25, 3],
    [100, 11],
  ];
  for (const [lines, want] of cases) {
    assert.equal(levelForLines(lines), want, `${lines} строк`);
  }
});

test("A5: интервал падения 800 мс на уровне 1 и на 70 мс меньше за уровень", () => {
  const cases = [
    [1, 800],
    [2, 730],
    [5, 520],
    [11, 100],
  ];
  for (const [level, want] of cases) {
    assert.equal(dropInterval(level), want, `уровень ${level}`);
  }
});

test("A5: интервал падения не опускается ниже 80 мс", () => {
  assert.equal(dropInterval(12), 80);
  assert.equal(dropInterval(30), 80);
});

test("A5: десятая удалённая строка повышает уровень до 2", () => {
  const filled = rowExcept(19, [3, 4, 5, 6]);
  const state = stateWith({ type: "I", rotation: 0, x: 3, y: 18 }, filled, { lines: 9 });
  const after = tick(state);
  assert.equal(after.level, 2);
  // Очки начисляются по уровню, который был до удаления строки.
  assert.equal(after.score, 100);
});

// ---------- A6: конец игры ----------

// O лежит на дне; следующая — T. Её точка появления: (4,0), (3,1), (4,1), (5,1).
const RESTING_O = { type: "O", rotation: 0, x: 0, y: 18 };

test("A6: новая игра не окончена", () => {
  assert.equal(createGame(1).over, false);
});

test("A6: если новая фигура не помещается в точку появления — игра окончена", () => {
  const state = stateWith(RESTING_O, [[4, 1]], { next: "T" });
  assert.equal(tick(state).over, true);
});

test("A6: новая фигура рядом с занятой клеткой игру не завершает", () => {
  const state = stateWith(RESTING_O, [[3, 0]], { next: "T" });
  assert.equal(tick(state).over, false);
});

test("A6: после конца игры ходы, поворот и падение ничего не меняют", () => {
  const over = { ...stateWith(spawnPiece("T")), over: true };
  for (const action of [moveLeft, moveRight, rotate, softDrop, hardDrop, tick]) {
    assert.deepEqual(action(over), over, action.name);
  }
});

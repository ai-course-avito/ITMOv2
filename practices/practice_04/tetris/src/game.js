// Игровая логика тетриса: чистые функции над обычным объектом состояния.
// Без DOM, таймеров и Math.random — случайность только из переданного seed.

export const BOARD_WIDTH = 10;
export const BOARD_HEIGHT = 20;
export const PIECE_TYPES = ["I", "O", "T", "S", "Z", "J", "L"];

// Базовые матрицы (поворот 0). Остальные повороты — поворот матрицы по часовой.
const SHAPES = {
  I: ["....", "####", "....", "...."],
  O: ["##", "##"],
  T: [".#.", "###", "..."],
  S: [".##", "##.", "..."],
  Z: ["##.", ".##", "..."],
  J: ["#..", "###", "..."],
  L: ["..#", "###", "..."],
};

function rotateMatrix(rows) {
  const n = rows.length;
  const out = [];
  for (let r = 0; r < n; r++) {
    let line = "";
    for (let c = 0; c < n; c++) line += rows[n - 1 - c][r];
    out.push(line);
  }
  return out;
}

const ROTATIONS = Object.fromEntries(
  Object.entries(SHAPES).map(([type, base]) => {
    const states = [base];
    for (let i = 1; i < 4; i++) states.push(rotateMatrix(states[i - 1]));
    return [type, states];
  }),
);

// Клетки фигуры на поле: массив [x, y] построчно сверху вниз, слева направо.
export function pieceCells(piece) {
  const rows = ROTATIONS[piece.type][piece.rotation];
  const cells = [];
  rows.forEach((line, r) => {
    for (let c = 0; c < line.length; c++) {
      if (line[c] === "#") cells.push([piece.x + c, piece.y + r]);
    }
  });
  return cells;
}

// Фигура помещается: все клетки внутри поля и не заняты.
export function fits(board, piece) {
  return pieceCells(piece).every(
    ([x, y]) => x >= 0 && x < BOARD_WIDTH && y >= 0 && y < BOARD_HEIGHT && board[y][x] === null,
  );
}

function tryPlace(state, piece) {
  return fits(state.board, piece) ? { ...state, active: piece } : state;
}

export function moveLeft(state) {
  if (state.over) return state;
  return tryPlace(state, { ...state.active, x: state.active.x - 1 });
}

export function moveRight(state) {
  if (state.over) return state;
  return tryPlace(state, { ...state.active, x: state.active.x + 1 });
}

const KICKS = [0, -1, 1, -2, 2];

// Поворот по часовой; если на месте не помещается — сдвиги KICKS, иначе отмена.
export function rotate(state) {
  if (state.over) return state;
  const { active } = state;
  const rotation = (active.rotation + 1) % 4;
  for (const dx of KICKS) {
    const candidate = { ...active, rotation, x: active.x + dx };
    if (fits(state.board, candidate)) return { ...state, active: candidate };
  }
  return state;
}

export function spawnPiece(type) {
  const width = SHAPES[type].length;
  return { type, rotation: 0, x: Math.floor((BOARD_WIDTH - width) / 2), y: 0 };
}

// ---------- генератор «мешок из 7» ----------

// mulberry32: возвращает [число в [0, 1), следующее состояние].
function nextRandom(rng) {
  const next = (rng + 0x6d2b79f5) >>> 0;
  let t = next;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return [((t ^ (t >>> 14)) >>> 0) / 4294967296, next];
}

function shuffledBag(rng) {
  const bag = [...PIECE_TYPES];
  let state = rng;
  for (let i = bag.length - 1; i > 0; i--) {
    let r;
    [r, state] = nextRandom(state);
    const j = Math.floor(r * (i + 1));
    [bag[i], bag[j]] = [bag[j], bag[i]];
  }
  return [bag, state];
}

// Берёт следующую фигуру из мешка; пустой мешок перетасовывается заново.
function drawPiece({ bag, rng }) {
  let nextBag = bag;
  let nextRng = rng;
  if (nextBag.length === 0) [nextBag, nextRng] = shuffledBag(nextRng);
  return { type: nextBag[0], bag: nextBag.slice(1), rng: nextRng };
}

export function pieceSequence(seed, count) {
  let source = { bag: [], rng: seed >>> 0 };
  const out = [];
  for (let i = 0; i < count; i++) {
    const drawn = drawPiece(source);
    out.push(drawn.type);
    source = drawn;
  }
  return out;
}

export function createGame(seed) {
  const first = drawPiece({ bag: [], rng: seed >>> 0 });
  const second = drawPiece(first);
  return {
    board: Array.from({ length: BOARD_HEIGHT }, emptyRow),
    active: spawnPiece(first.type),
    next: second.type,
    bag: second.bag,
    rng: second.rng,
    score: 0,
    lines: 0,
    level: 1,
    over: false,
    hold: null,
    holdUsed: false,
  };
}

// ---------- спуск и фиксация ----------

function emptyRow() {
  return Array(BOARD_WIDTH).fill(null);
}

// Убирает заполненные строки; сверху добавляются пустые.
function clearLines(board) {
  const kept = board.filter((row) => row.some((cell) => cell === null));
  const cleared = BOARD_HEIGHT - kept.length;
  return { board: [...Array.from({ length: cleared }, emptyRow), ...kept], cleared };
}

// Записывает активную фигуру в поле, удаляет строки и выводит следующую.
// Если следующая не помещается в точку появления — игра окончена.
function lockPiece(state) {
  const placed = state.board.map((row) => [...row]);
  for (const [x, y] of pieceCells(state.active)) placed[y][x] = state.active.type;
  const { board, cleared } = clearLines(placed);
  const drawn = drawPiece(state);
  const active = spawnPiece(state.next);
  return {
    ...state,
    board,
    score: state.score + lineClearPoints(cleared, state.level),
    lines: state.lines + cleared,
    level: levelForLines(state.lines + cleared),
    active,
    over: !fits(board, active),
    holdUsed: false,
    next: drawn.type,
    bag: drawn.bag,
    rng: drawn.rng,
  };
}

function movedDown(piece) {
  return { ...piece, y: piece.y + 1 };
}

const LINE_POINTS = [0, 100, 300, 500, 800];

export function lineClearPoints(lines, level) {
  return LINE_POINTS[lines] * level;
}

export function levelForLines(lines) {
  return 1 + Math.floor(lines / 10);
}

// Интервал гравитации в мс для уровня.
export function dropInterval(level) {
  return Math.max(80, 800 - (level - 1) * 70);
}

// Шаг гравитации: опустить на клетку или, если некуда, зафиксировать.
export function tick(state) {
  if (state.over) return state;
  const down = movedDown(state.active);
  if (!fits(state.board, down)) return lockPiece(state);
  return { ...state, active: down };
}

export function softDrop(state) {
  if (state.over) return state;
  const down = movedDown(state.active);
  if (!fits(state.board, down)) return lockPiece(state);
  return { ...state, active: down, score: state.score + 1 };
}

// B1: позиция, куда упадёт активная фигура при жёстком сбросе (призрачная фигура).
export function ghostPiece(state) {
  let piece = state.active;
  while (fits(state.board, movedDown(piece))) piece = movedDown(piece);
  return piece;
}

// B2: текущая фигура откладывается, на её место в точку появления выходит
// отложенная (или следующая из очереди, если отложенной ещё нет).
// Не чаще раза до фиксации фигуры; если выходящей фигуре некуда встать — отмена.
export function hold(state) {
  if (state.over || state.holdUsed) return state;
  const fromQueue = state.hold === null;
  const active = spawnPiece(fromQueue ? state.next : state.hold);
  if (!fits(state.board, active)) return state;
  const held = { ...state, active, hold: state.active.type, holdUsed: true };
  if (!fromQueue) return held;
  const drawn = drawPiece(state);
  return { ...held, next: drawn.type, bag: drawn.bag, rng: drawn.rng };
}

export function hardDrop(state) {
  if (state.over) return state;
  const landed = ghostPiece(state);
  const distance = landed.y - state.active.y;
  return lockPiece({ ...state, active: landed, score: state.score + 2 * distance });
}

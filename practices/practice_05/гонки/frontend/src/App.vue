<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import ReportErrorButton from "./ReportErrorButton.vue";
import Leaderboard from "./Leaderboard.vue";
import { createRaceScene } from "./scene3d.js";
import { getLeaderboard, saveRaceResult } from "./api.js";
import {
  MAX_NAME_LENGTH,
  nameLength,
  clampName,
  normalizeName,
  validateNames,
  formatTime,
  pickWinner,
  leaderboardState,
  isLapTimeSavable,
  nameKey,
} from "./raceLogic.js";

const API_URL = "http://localhost:8000/select-car";

// 3 модельки
const CAR_MODELS = [
  { id: "racer", name: "Спорткар", speed: 4.8, turnSpeed: 0.055, icon: "🏎️" },
  { id: "drifter", name: "Дрифтер", speed: 4.4, turnSpeed: 0.07, icon: "🚗" },
  { id: "tank", name: "Внедорожник", speed: 4.0, turnSpeed: 0.045, icon: "🚙" },
];

// 3 пастельных цвета (красный, жёлтый, фиолетовый)
const CAR_COLORS = [
  { id: "red", name: "Пастельный красный", hex: "#F87171", light: "#FCA5A5" },
  { id: "yellow", name: "Пастельный жёлтый", hex: "#FBBF24", light: "#FDE047" },
  { id: "purple", name: "Пастельный фиолетовый", hex: "#C084FC", light: "#E9D5FF" },
];

// Состояние игры: 'select' | 'countdown' | 'racing' | 'gameover'
const gameState = ref("select");

// Выбор игроков
const p1Model = ref("racer");
const p1Color = ref("red");

const p2Model = ref("drifter");
const p2Color = ref("purple");

// Имена игроков: живут всю сессию вкладки, «Новая игра» их не сбрасывает
const p1Name = ref("Игрок 1");
const p2Name = ref("Игрок 2");
const nameErrors = ref({ p1: null, p2: null }); // null | "empty" | "duplicate"
let isComposing = false; // идёт IME-набор — не обрезаем посреди символа

function nameRef(player) {
  return player === 1 ? p1Name : p2Name;
}

function applyNameInput(player, input) {
  const clamped = clampName(input.value);
  // Vue не перерисует поле, если обрезанное значение совпало со старым, — пишем сами
  if (clamped !== input.value) input.value = clamped;
  nameRef(player).value = clamped;
  const key = player === 1 ? "p1" : "p2";
  const otherKey = player === 1 ? "p2" : "p1";
  const errors = { ...nameErrors.value, [key]: null };
  if (errors[otherKey] === "duplicate") errors[otherKey] = null;
  nameErrors.value = errors;
}

function onNameInput(player, event) {
  if (isComposing) return;
  applyNameInput(player, event.target);
}

function onNameCompositionStart() {
  isComposing = true;
}

function onNameCompositionEnd(player, event) {
  isComposing = false;
  applyNameInput(player, event.target);
}

const countdown = ref(3);
const winner = ref(null);

// Часы гонки: монотонные (performance.now), одно показание на кадр — по нему и
// таймер, и время круга. Время скрытой вкладки тоже входит (часы не стоят).
let raceStartMs = null;
const elapsedMs = ref(0);
let frameFinishers = []; // кто достиг финиша в текущем кадре
const errorMessage = ref("");

// Canvas и анимация
const canvasRef = ref(null);
let animationFrameId = null;

// 3D-сцена (см. scene3d.js): создаётся при первом кадре гонки, когда canvas уже в DOM
let raceScene = null;
const sceneError = ref("");

// Трасса (овал/кольцо)
const trackConfig = {
  cx: 400,
  cy: 250,
  rx: 310,
  ry: 180,
  width: 90,
  finishAngle: -Math.PI / 2, // финиш вверху (угол -90 град)
};

// Физика машинок
const keysDown = {};

const p1State = {
  x: 400,
  y: 110,
  angle: 0,
  speed: 0,
  lapAngle: 0,
  prevAngle: 0,
  progress: 0,
  finished: false,
};

const p2State = {
  x: 400,
  y: 70,
  angle: 0,
  speed: 0,
  lapAngle: 0,
  prevAngle: 0,
  progress: 0,
  finished: false,
};

function onKeyDown(e) {
  keysDown[e.code] = true;
  // Предотвратить скролл стрелками во время игры
  if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) {
    if (gameState.value === "racing") {
      e.preventDefault();
    }
  }
}

function onKeyUp(e) {
  keysDown[e.code] = false;
}

// Таблица рекордов: грузится при открытии сайта, при возврате на «Выбор»,
// после сохранения результата и по «Повторить». Ошибка не мешает играть.
const board = ref(null);
const boardStatus = ref("loading"); // "loading" | "ready" | "error"
let boardController = null;

async function loadLeaderboard() {
  boardController?.abort();
  const controller = new AbortController();
  boardController = controller;
  boardStatus.value = "loading";
  const result = await getLeaderboard({ signal: controller.signal });
  if (result.ok) {
    board.value = result.data;
    boardStatus.value = "ready";
  } else if (result.kind !== "aborted") {
    boardStatus.value = "error";
  }
}

// Сохранение времени победителя на «Финише».
// "saving" | "saved" | "error" | "rejected" | "out_of_range" | null
const saveStatus = ref(null);
const newRecordKey = ref(null);
let finishController = null;
let finishGeneration = 0; // ответ от прерванного сохранения не применяется

async function saveAndRefresh() {
  const generation = ++finishGeneration;
  finishController?.abort();
  const controller = new AbortController();
  finishController = controller;
  newRecordKey.value = null;

  // Время вне 3000–5 999 999 мс сервер не примет — не отправляем вовсе
  if (!isLapTimeSavable(winner.value.lapTimeMs)) {
    saveStatus.value = "out_of_range";
    loadLeaderboard();
    return;
  }

  saveStatus.value = "saving";
  const result = await saveRaceResult(
    { name: winner.value.name, lapTimeMs: winner.value.lapTimeMs },
    { signal: controller.signal },
  );
  if (generation !== finishGeneration || (!result.ok && result.kind === "aborted")) return;

  if (result.ok) {
    saveStatus.value = "saved";
    newRecordKey.value = result.data.is_new_record ? nameKey(result.data.name) : null;
  } else {
    saveStatus.value = result.kind === "rejected" ? "rejected" : "error";
  }
  loadLeaderboard();
}

onMounted(() => {
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);
  loadLeaderboard();
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeyDown);
  window.removeEventListener("keyup", onKeyUp);
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  disposeScene();
});

// Старт гонки через бэкенд валидацию для обоих игроков
async function prepareAndStartRace() {
  errorMessage.value = "";

  // Имена проверяются до сервера: пустое или одинаковые — гонка не стартует
  p1Name.value = normalizeName(p1Name.value);
  p2Name.value = normalizeName(p2Name.value);
  nameErrors.value = validateNames(p1Name.value, p2Name.value);
  if (nameErrors.value.p1 || nameErrors.value.p2) return;

  try {
    // Валидируем выбор обоих игроков через бэкенд
    const [res1, res2] = await Promise.all([
      fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: p1Model.value, color: p1Color.value }),
      }),
      fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: p2Model.value, color: p2Color.value }),
      }),
    ]);

    if (!res1.ok || !res2.ok) {
      throw new Error("Ошибка проверки выбора машинки сервером.");
    }

    startCountdown();
  } catch (err) {
    errorMessage.value = "Не удалось подтвердить старт у сервера. Проверьте запуск бэкенда.";
  }
}

function startCountdown() {
  gameState.value = "countdown";
  countdown.value = 3;
  sceneError.value = "";

  initCars();

  const timer = setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0) {
      clearInterval(timer);
      gameState.value = "racing";
      raceStartMs = performance.now();
      elapsedMs.value = 0;
      frameFinishers = [];
      runGameLoop();
    }
  }, 1000);
}

function initCars() {
  p1State.x = 400;
  p1State.y = 100;
  p1State.angle = 0; // направление вправо
  p1State.speed = 0;
  p1State.progress = 0;
  p1State.prevAngle = -Math.PI / 2;
  p1State.finished = false;

  p2State.x = 400;
  p2State.y = 65;
  p2State.angle = 0;
  p2State.speed = 0;
  p2State.progress = 0;
  p2State.prevAngle = -Math.PI / 2;
  p2State.finished = false;

  winner.value = null;
}

function runGameLoop() {
  if (gameState.value !== "racing") return;

  const now = performance.now();
  updatePhysics();
  if (resolveFinish(now)) return;
  elapsedMs.value = now - raceStartMs;
  drawScene();

  // 3D недоступно: гонку не продолжаем, пользователь видит сообщение
  if (sceneError.value) return;

  if (gameState.value === "racing") {
    animationFrameId = requestAnimationFrame(runGameLoop);
  }
}

function getModelParams(id) {
  return CAR_MODELS.find((m) => m.id === id) || CAR_MODELS[0];
}

function getColorHex(id) {
  return CAR_COLORS.find((c) => c.id === id)?.hex || "#F87171";
}

function updatePhysics() {
  const m1 = getModelParams(p1Model.value);
  const m2 = getModelParams(p2Model.value);

  // --- Игрок 1: W/A/S/D ---
  if (keysDown["KeyW"]) {
    p1State.speed = Math.min(p1State.speed + 0.15, m1.speed);
  } else if (keysDown["KeyS"]) {
    // Не даём ехать назад больше минимальной скорости для манёвра
    p1State.speed = Math.max(p1State.speed - 0.12, -0.6);
  } else {
    p1State.speed *= 0.96; // трение
  }

  if (Math.abs(p1State.speed) > 0.05) {
    if (keysDown["KeyA"]) p1State.angle -= m1.turnSpeed * (p1State.speed > 0 ? 1 : -1);
    if (keysDown["KeyD"]) p1State.angle += m1.turnSpeed * (p1State.speed > 0 ? 1 : -1);
  }

  p1State.x += Math.cos(p1State.angle) * p1State.speed;
  p1State.y += Math.sin(p1State.angle) * p1State.speed;
  keepInsideTrack(p1State);
  checkLap(p1State, 1);

  // --- Игрок 2: Стрелки (ArrowUp, ArrowDown, ArrowLeft, ArrowRight) ---
  if (keysDown["ArrowUp"]) {
    p2State.speed = Math.min(p2State.speed + 0.15, m2.speed);
  } else if (keysDown["ArrowDown"]) {
    // Не даём ехать назад больше минимальной скорости для манёвра
    p2State.speed = Math.max(p2State.speed - 0.12, -0.6);
  } else {
    p2State.speed *= 0.96;
  }

  if (Math.abs(p2State.speed) > 0.05) {
    if (keysDown["ArrowLeft"]) p2State.angle -= m2.turnSpeed * (p2State.speed > 0 ? 1 : -1);
    if (keysDown["ArrowRight"]) p2State.angle += m2.turnSpeed * (p2State.speed > 0 ? 1 : -1);
  }

  p2State.x += Math.cos(p2State.angle) * p2State.speed;
  p2State.y += Math.sin(p2State.angle) * p2State.speed;
  keepInsideTrack(p2State);
  checkLap(p2State, 2);
}

// Ограничение движения границами трассы (отскок от бордюров)
function keepInsideTrack(car) {
  const dx = car.x - trackConfig.cx;
  const dy = car.y - trackConfig.cy;
  const angle = Math.atan2(dy, dx);

  // Радиусы центра трассы под текущим углом эллипса
  const rCenter = Math.sqrt(
    1 / (Math.pow(Math.cos(angle) / trackConfig.rx, 2) + Math.pow(Math.sin(angle) / trackConfig.ry, 2))
  );

  const halfWidth = trackConfig.width / 2 - 10; // с учётом размера машинки
  const rMin = rCenter - halfWidth;
  const rMax = rCenter + halfWidth;

  const currentDist = Math.sqrt(dx * dx + dy * dy);

  if (currentDist < rMin) {
    // Столкновение с внутренним бордюром
    car.x = trackConfig.cx + Math.cos(angle) * rMin;
    car.y = trackConfig.cy + Math.sin(angle) * rMin;
    car.speed *= 0.4;
  } else if (currentDist > rMax) {
    // Столкновение с внешним бордюром
    car.x = trackConfig.cx + Math.cos(angle) * rMax;
    car.y = trackConfig.cy + Math.sin(angle) * rMax;
    car.speed *= 0.4;
  }
}

// Проверка круга через угловое перемещение вокруг центра кольца (по часовой стрелке)
function checkLap(car, playerNum) {
  const dx = car.x - trackConfig.cx;
  const dy = car.y - trackConfig.cy;
  const angle = Math.atan2(dy, dx); // [-PI, PI]

  let diff = angle - car.prevAngle;
  // нормализация перехода через -PI / +PI
  if (diff < -Math.PI) diff += 2 * Math.PI;
  if (diff > Math.PI) diff -= 2 * Math.PI;

  // Идём по часовой стрелке (угол увеличивается)
  if (diff > 0 && diff < 1.0) {
    car.progress += diff;
  }

  car.prevAngle = angle;

  // Один полный круг = 2 * PI радиан (~6.28)
  if (car.progress >= 2 * Math.PI - 0.15 && !car.finished) {
    car.finished = true;
    declareWinner(playerNum);
  }
}

// Вызывается из checkLap: только запоминает финишировавшего в этом кадре.
// Победителя выбирает resolveFinish после обработки обеих машинок — иначе при
// финише в одном кадре игрок 2 всегда перезаписывал бы игрока 1.
function declareWinner(playerNum) {
  if (!frameFinishers.includes(playerNum)) frameFinishers.push(playerNum);
}

function resolveFinish(now) {
  if (frameFinishers.length === 0) return false;
  const playerNum = pickWinner(frameFinishers, Math.random);
  winner.value = {
    player: playerNum,
    name: playerNum === 1 ? p1Name.value : p2Name.value,
    model: playerNum === 1 ? getModelParams(p1Model.value).name : getModelParams(p2Model.value).name,
    color: playerNum === 1 ? p1Color.value : p2Color.value,
    hex: playerNum === 1 ? getColorHex(p1Color.value) : getColorHex(p2Color.value),
    lapTimeMs: Math.round(now - raceStartMs),
  };
  gameState.value = "gameover";
  saveAndRefresh();
  return true;
}

function resetGame() {
  gameState.value = "select";
  winner.value = null;
  errorMessage.value = "";
  sceneError.value = "";
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  // «Новая игра» во время сохранения: запрос отменяется, его ответ не показывается
  finishGeneration++;
  finishController?.abort();
  saveStatus.value = null;
  newRecordKey.value = null;
  loadLeaderboard();
}

function disposeScene() {
  if (raceScene) {
    raceScene.dispose();
    raceScene = null;
  }
}

function drawScene() {
  const canvas = canvasRef.value;
  if (!canvas) return;

  if (!raceScene) {
    try {
      raceScene = createRaceScene(canvas, trackConfig, [
        { modelId: p1Model.value, colorHex: getColorHex(p1Color.value), label: "P1" },
        { modelId: p2Model.value, colorHex: getColorHex(p2Color.value), label: "P2" },
      ]);
    } catch (err) {
      sceneError.value =
        "3D-трасса недоступна: браузер не поддерживает 3D (WebGL). Попробуйте другой браузер.";
      return;
    }
  }

  raceScene.render([p1State, p2State]);
}

// Сцена живёт только пока идёт гонка: при выходе из «racing» освобождаем ресурсы,
// чтобы повторные запуски не копили WebGL-контексты
watch(gameState, (state) => {
  if (state !== "racing") disposeScene();
});
</script>

<template>
  <main class="page">
    <header class="header">
      <span class="badge">VINTAGE RACING ARENA</span>
      <h1 class="title">ГОНКИ НА ДВОИХ</h1>
      <p class="subtitle">1 полный круг по кольцу • W/A/S/D против Стрелок</p>
    </header>

    <!-- СЛАЙД 1: ВЫБОР МАШИНОК И ЦВЕТОВ -->
    <div v-if="gameState === 'select'" class="selection-box">
      <div class="players-columns">
        <!-- Игрок 1 -->
        <div class="player-card">
          <div class="player-header p1-accent">
            <h2>🏎️ Игрок 1</h2>
            <span class="controls-hint">Управление: W, A, S, D</span>
          </div>

          <div class="form-section">
            <label class="label" for="p1-name">Имя:</label>
            <div class="name-row">
              <input
                id="p1-name"
                class="name-input"
                :class="{ invalid: nameErrors.p1 }"
                type="text"
                autocomplete="off"
                :value="p1Name"
                @input="onNameInput(1, $event)"
                @compositionstart="onNameCompositionStart"
                @compositionend="onNameCompositionEnd(1, $event)"
              />
              <span class="name-counter">{{ nameLength(p1Name) }}/{{ MAX_NAME_LENGTH }}</span>
            </div>
            <span v-if="nameErrors.p1 === 'empty'" class="name-error">Введите имя</span>
          </div>

          <div class="form-section">
            <span class="label">Модель:</span>
            <div class="option-row">
              <button
                v-for="m in CAR_MODELS"
                :key="m.id"
                class="choice-btn"
                :class="{ active: p1Model === m.id }"
                @click="p1Model = m.id"
              >
                {{ m.icon }} {{ m.name }}
              </button>
            </div>
          </div>

          <div class="form-section">
            <span class="label">Пастельный цвет:</span>
            <div class="option-row">
              <button
                v-for="c in CAR_COLORS"
                :key="c.id"
                class="choice-btn color-choice"
                :class="{ active: p1Color === c.id }"
                @click="p1Color = c.id"
              >
                <span class="dot" :style="{ backgroundColor: c.hex }"></span>
                {{ c.name }}
              </button>
            </div>
          </div>
        </div>

        <!-- Игрок 2 -->
        <div class="player-card">
          <div class="player-header p2-accent">
            <h2>🚗 Игрок 2</h2>
            <span class="controls-hint">Управление: Стрелочки (↑, ←, ↓, →)</span>
          </div>

          <div class="form-section">
            <label class="label" for="p2-name">Имя:</label>
            <div class="name-row">
              <input
                id="p2-name"
                class="name-input"
                :class="{ invalid: nameErrors.p2 }"
                type="text"
                autocomplete="off"
                :value="p2Name"
                @input="onNameInput(2, $event)"
                @compositionstart="onNameCompositionStart"
                @compositionend="onNameCompositionEnd(2, $event)"
              />
              <span class="name-counter">{{ nameLength(p2Name) }}/{{ MAX_NAME_LENGTH }}</span>
            </div>
            <span v-if="nameErrors.p2 === 'empty'" class="name-error">Введите имя</span>
          </div>

          <div class="form-section">
            <span class="label">Модель:</span>
            <div class="option-row">
              <button
                v-for="m in CAR_MODELS"
                :key="m.id"
                class="choice-btn"
                :class="{ active: p2Model === m.id }"
                @click="p2Model = m.id"
              >
                {{ m.icon }} {{ m.name }}
              </button>
            </div>
          </div>

          <div class="form-section">
            <span class="label">Пастельный цвет:</span>
            <div class="option-row">
              <button
                v-for="c in CAR_COLORS"
                :key="c.id"
                class="choice-btn color-choice"
                :class="{ active: p2Color === c.id }"
                @click="p2Color = c.id"
              >
                <span class="dot" :style="{ backgroundColor: c.hex }"></span>
                {{ c.name }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="nameErrors.p1 === 'duplicate'" class="error-banner">
        ⚠️ Имена игроков должны различаться
      </div>

      <div v-if="errorMessage" class="error-banner">
        ⚠️ {{ errorMessage }}
      </div>

      <button class="btn-start-race" @click="prepareAndStartRace">
        🏁 Начать заезд!
      </button>

      <Leaderboard
        :state="leaderboardState(board, boardStatus)"
        :board="board"
        :new-record-key="null"
        @retry="loadLeaderboard"
      />
    </div>

    <!-- СЛАЙД 2: ОБРАТНЫЙ ОТСЧЁТ -->
    <div v-else-if="gameState === 'countdown'" class="countdown-overlay">
      <div class="countdown-number">{{ countdown }}</div>
      <p>Приготовьтесь к старту!</p>
    </div>

    <!-- СЛАЙД 3: ТРАССА И САМА ГОНКА -->
    <div v-else-if="gameState === 'racing'" class="racing-container">
      <div class="race-hud">
        <div class="hud-item" :style="{ color: getColorHex(p1Color) }">
          <strong>{{ p1Name }} (W/A/S/D):</strong> {{ Math.min(100, Math.round((p1State.progress / (2 * Math.PI)) * 100)) }}%
        </div>
        <div class="hud-item hud-timer">
          <span v-if="!sceneError" class="timer-value">{{ formatTime(elapsedMs) }}</span>
          <span class="finish-label">🏁 1 КРУГ</span>
        </div>
        <div class="hud-item" :style="{ color: getColorHex(p2Color) }">
          <strong>{{ p2Name }} (Стрелки):</strong> {{ Math.min(100, Math.round((p2State.progress / (2 * Math.PI)) * 100)) }}%
        </div>
      </div>

      <div v-if="sceneError" class="error-banner scene-error">
        ⚠️ {{ sceneError }}
        <button class="btn-new-game" @click="resetGame">Назад к выбору</button>
      </div>

      <canvas
        v-show="!sceneError"
        ref="canvasRef"
        width="800"
        height="500"
        class="race-canvas"
      ></canvas>
    </div>

    <!-- СЛАЙД 4: ФИНАЛЬНЫЙ СЛАЙД / ПОБЕДИТЕЛЬ -->
    <div v-else-if="gameState === 'gameover'" class="victory-slide">
      <div class="trophy-icon">🏆</div>
      <h2 class="victory-title" :style="{ color: winner.hex }">
        ПОБЕДИЛ {{ winner.name.toUpperCase() }}!
      </h2>
      <p class="victory-details">
        Болид: <strong>{{ winner.model }}</strong> | Первый завершил круг!
      </p>
      <p class="lap-time">
        Время круга: <strong>{{ formatTime(winner.lapTimeMs) }}</strong>
      </p>

      <div v-if="saveStatus === 'saving'" class="save-status">Сохраняем результат…</div>
      <div v-else-if="saveStatus === 'saved'" class="save-status save-ok">Результат сохранён ✓</div>
      <div v-else-if="saveStatus === 'error'" class="save-status save-fail">
        <span>Не удалось сохранить результат</span>
        <button class="lb-retry-btn" @click="saveAndRefresh">Повторить</button>
      </div>
      <div v-else-if="saveStatus === 'rejected'" class="save-status save-fail">
        Результат не сохранён: некорректные данные
      </div>
      <div v-else-if="saveStatus === 'out_of_range'" class="save-status save-fail">
        Результат не сохранён: время вне допустимого диапазона
      </div>

      <button class="btn-new-game" @click="resetGame">
        🔄 Новая игра
      </button>

      <Leaderboard
        :state="leaderboardState(board, boardStatus)"
        :board="board"
        :new-record-key="newRecordKey"
        @retry="loadLeaderboard"
      />
    </div>

    <ReportErrorButton />
  </main>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  text-align: center;
  padding: 30px 16px;
  background: radial-gradient(circle at 50% 20%, #1a1033 0%, #0d0a1f 100%);
  color: #f5f3ff;
  box-sizing: border-box;
  font-family: inherit;
}

.header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.badge {
  font-size: 0.75rem;
  letter-spacing: 0.25em;
  color: #22d3ee;
  border: 1px solid rgba(34, 211, 238, 0.4);
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.05);
}

.title {
  font-size: 3rem;
  margin: 0;
  font-weight: 900;
  letter-spacing: 0.08em;
  background: linear-gradient(135deg, #8b5cf6 0%, #22d3ee 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: #c084fc;
  margin: 0;
  font-size: 0.95rem;
}

/* Экран выбора */
.selection-box {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: min(850px, 95vw);
  background: rgba(26, 16, 51, 0.7);
  border: 1px solid rgba(139, 92, 246, 0.3);
  padding: 24px;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
}

.players-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

@media (max-width: 650px) {
  .players-columns {
    grid-template-columns: 1fr;
  }
}

.player-card {
  background: #0d0a1f;
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 12px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  text-align: left;
}

.player-header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.p1-accent h2 {
  color: #f87171;
}

.p2-accent h2 {
  color: #c084fc;
}

.controls-hint {
  font-size: 0.8rem;
  color: #94a3b8;
  display: block;
  margin-top: 4px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label {
  font-size: 0.85rem;
  color: #22d3ee;
  font-weight: 600;
}

.option-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* Поле имени */
.name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.name-input {
  flex: 1;
  min-width: 0;
  background: #1a1033;
  color: #f5f3ff;
  border: 1px solid rgba(139, 92, 246, 0.3);
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: inherit;
}

.name-input:focus {
  outline: none;
  border-color: #22d3ee;
}

.name-input.invalid {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.name-counter {
  font-size: 0.75rem;
  color: #a78bfa;
  font-variant-numeric: tabular-nums;
}

.name-error {
  font-size: 0.8rem;
  color: #fca5a5;
  text-align: left;
}

.choice-btn {
  background: #1a1033;
  color: #f5f3ff;
  border: 1px solid rgba(139, 92, 246, 0.3);
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s ease;
}

.choice-btn:hover {
  border-color: #22d3ee;
}

.choice-btn.active {
  background: rgba(34, 211, 238, 0.15);
  border-color: #22d3ee;
  color: #22d3ee;
  font-weight: 700;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.btn-start-race {
  background: linear-gradient(135deg, #8b5cf6 0%, #22d3ee 100%);
  color: #0d0a1f;
  font-size: 1.2rem;
  font-weight: 800;
  padding: 14px 28px;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(34, 211, 238, 0.4);
  transition: transform 0.2s ease;
  margin-top: 8px;
}

.btn-start-race:hover {
  transform: translateY(-2px);
}

.error-banner {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid #ef4444;
  color: #fca5a5;
  padding: 10px;
  border-radius: 8px;
}

/* Обратный отсчёт */
.countdown-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 400px;
}

.countdown-number {
  font-size: 6rem;
  font-weight: 900;
  color: #22d3ee;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.9); opacity: 0.8; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.8; }
}

/* Трасса */
.racing-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.race-hud {
  display: flex;
  justify-content: space-between;
  width: 800px;
  max-width: 95vw;
  font-size: 0.95rem;
  padding: 8px 16px;
  background: #0d0a1f;
  border: 1px solid #8b5cf6;
  border-radius: 8px;
}

.finish-label {
  color: #facc15;
  font-weight: bold;
}

.hud-timer {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.timer-value {
  color: #f5f3ff;
  font-size: 1.15rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.hud-timer .finish-label {
  font-size: 0.75rem;
}

.lap-time {
  font-size: 1.3rem;
  color: #22d3ee;
  margin: 0;
  font-variant-numeric: tabular-nums;
}

.scene-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 800px;
  max-width: 95vw;
  box-sizing: border-box;
}

.race-canvas {
  border: 2px solid #8b5cf6;
  border-radius: 12px;
  box-shadow: 0 0 30px rgba(139, 92, 246, 0.3);
  max-width: 95vw;
  height: auto;
}

/* Финальный экран победы */
.victory-slide {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  background: rgba(26, 16, 51, 0.8);
  border: 2px solid #22d3ee;
  padding: 40px;
  border-radius: 16px;
  box-shadow: 0 0 35px rgba(34, 211, 238, 0.3);
  animation: popIn 0.3s ease-out;
}

@keyframes popIn {
  from { transform: scale(0.85); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.trophy-icon {
  font-size: 4rem;
}

.victory-title {
  font-size: 2.5rem;
  margin: 0;
  font-weight: 900;
}

.victory-details {
  font-size: 1.1rem;
  color: #cbd5e1;
  margin: 0;
}

.btn-new-game {
  background: linear-gradient(135deg, #8b5cf6 0%, #22d3ee 100%);
  color: #0d0a1f;
  font-size: 1.1rem;
  font-weight: 800;
  padding: 12px 30px;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  margin-top: 12px;
  box-shadow: 0 4px 16px rgba(34, 211, 238, 0.4);
  transition: transform 0.2s;
}

.btn-new-game:hover {
  transform: translateY(-2px);
}

/* Статус сохранения результата */
.save-status {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 14px;
  border-radius: 8px;
  color: #cbd5e1;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.3);
}

.save-ok {
  color: #86efac;
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.4);
}

.save-fail {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.12);
  border-color: #ef4444;
}

.lb-retry-btn {
  background: #1a1033;
  color: #22d3ee;
  border: 1px solid #22d3ee;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
}

.victory-slide {
  width: min(560px, 95vw);
  box-sizing: border-box;
}
</style>

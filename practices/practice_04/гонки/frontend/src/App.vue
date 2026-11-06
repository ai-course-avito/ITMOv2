<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import ReportErrorButton from "./ReportErrorButton.vue";

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

const countdown = ref(3);
const winner = ref(null);
const errorMessage = ref("");

// Canvas и анимация
const canvasRef = ref(null);
let animationFrameId = null;

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

onMounted(() => {
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeyDown);
  window.removeEventListener("keyup", onKeyUp);
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
});

// Старт гонки через бэкенд валидацию для обоих игроков
async function prepareAndStartRace() {
  errorMessage.value = "";
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

  initCars();

  const timer = setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0) {
      clearInterval(timer);
      gameState.value = "racing";
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

  updatePhysics();
  drawScene();

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

function declareWinner(playerNum) {
  winner.value = {
    player: playerNum,
    name: playerNum === 1 ? "Игрок 1" : "Игрок 2",
    model: playerNum === 1 ? getModelParams(p1Model.value).name : getModelParams(p2Model.value).name,
    color: playerNum === 1 ? p1Color.value : p2Color.value,
    hex: playerNum === 1 ? getColorHex(p1Color.value) : getColorHex(p2Color.value),
  };
  gameState.value = "gameover";
}

function resetGame() {
  gameState.value = "select";
  winner.value = null;
  errorMessage.value = "";
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
}

function drawScene() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // Очистка
  ctx.fillStyle = "#0D0A1F";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Рисуем кольцевую трассу
  ctx.save();
  ctx.lineWidth = trackConfig.width;

  // Внешний асфальт трассы
  ctx.strokeStyle = "#1A1033";
  ctx.beginPath();
  ctx.ellipse(trackConfig.cx, trackConfig.cy, trackConfig.rx, trackConfig.ry, 0, 0, 2 * Math.PI);
  ctx.stroke();

  // Неоновые бордюры (внутренний и внешний)
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#8B5CF6";
  ctx.beginPath();
  ctx.ellipse(
    trackConfig.cx,
    trackConfig.cy,
    trackConfig.rx + trackConfig.width / 2,
    trackConfig.ry + trackConfig.width / 2,
    0,
    0,
    2 * Math.PI
  );
  ctx.stroke();

  ctx.strokeStyle = "#22D3EE";
  ctx.beginPath();
  ctx.ellipse(
    trackConfig.cx,
    trackConfig.cy,
    trackConfig.rx - trackConfig.width / 2,
    trackConfig.ry - trackConfig.width / 2,
    0,
    0,
    2 * Math.PI
  );
  ctx.stroke();

  // Разделительная пунктирная линия
  ctx.lineWidth = 2;
  ctx.strokeStyle = "rgba(192, 132, 252, 0.4)";
  ctx.setLineDash([12, 16]);
  ctx.beginPath();
  ctx.ellipse(trackConfig.cx, trackConfig.cy, trackConfig.rx, trackConfig.ry, 0, 0, 2 * Math.PI);
  ctx.stroke();
  ctx.setLineDash([]);

  // Линия старта / финиша
  const startX = trackConfig.cx;
  const startY1 = trackConfig.cy - trackConfig.ry - trackConfig.width / 2;
  const startY2 = trackConfig.cy - trackConfig.ry + trackConfig.width / 2;

  ctx.lineWidth = 6;
  ctx.strokeStyle = "#FFFFFF";
  ctx.beginPath();
  ctx.moveTo(startX, startY1);
  ctx.lineTo(startX, startY2);
  ctx.stroke();

  // Клетчатый узор финиша
  for (let i = 0; i < trackConfig.width; i += 10) {
    ctx.fillStyle = (i / 10) % 2 === 0 ? "#000000" : "#FFFFFF";
    ctx.fillRect(startX - 3, startY1 + i, 6, 10);
  }

  ctx.restore();

  // Рисуем машинку 1
  drawCar(ctx, p1State, getColorHex(p1Color.value), "P1");

  // Рисуем машинку 2
  drawCar(ctx, p2State, getColorHex(p2Color.value), "P2");
}

function drawCar(ctx, car, colorHex, label) {
  ctx.save();
  ctx.translate(car.x, car.y);
  ctx.rotate(car.angle);

  // Корпус машинки
  ctx.fillStyle = colorHex;
  ctx.shadowColor = colorHex;
  ctx.shadowBlur = 10;

  // Закруглённый прямоугольник машинки (32x18)
  ctx.beginPath();
  ctx.roundRect(-16, -9, 32, 18, 4);
  ctx.fill();

  // Колёса
  ctx.shadowBlur = 0;
  ctx.fillStyle = "#1E1B4B";
  ctx.fillRect(-12, -12, 8, 4);
  ctx.fillRect(4, -12, 8, 4);
  ctx.fillRect(-12, 8, 8, 4);
  ctx.fillRect(4, 8, 8, 4);

  // Лобовое стекло
  ctx.fillStyle = "#0D0A1F";
  ctx.fillRect(2, -6, 6, 12);

  // Фары
  ctx.fillStyle = "#FEF08A";
  ctx.fillRect(14, -7, 3, 4);
  ctx.fillRect(14, 3, 3, 4);

  // Подпись игрока сверху
  ctx.rotate(-car.angle);
  ctx.font = "bold 11px sans-serif";
  ctx.fillStyle = "#FFFFFF";
  ctx.textAlign = "center";
  ctx.fillText(label, 0, -16);

  ctx.restore();
}
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

      <div v-if="errorMessage" class="error-banner">
        ⚠️ {{ errorMessage }}
      </div>

      <button class="btn-start-race" @click="prepareAndStartRace">
        🏁 Начать заезд!
      </button>
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
          <strong>Игрок 1 (W/A/S/D):</strong> {{ Math.min(100, Math.round((p1State.progress / (2 * Math.PI)) * 100)) }}%
        </div>
        <div class="hud-item finish-label">🏁 ФИНИШ: 1 КРУГ</div>
        <div class="hud-item" :style="{ color: getColorHex(p2Color) }">
          <strong>Игрок 2 (Стрелки):</strong> {{ Math.min(100, Math.round((p2State.progress / (2 * Math.PI)) * 100)) }}%
        </div>
      </div>

      <canvas
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

      <button class="btn-new-game" @click="resetGame">
        🔄 Новая игра
      </button>
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
</style>

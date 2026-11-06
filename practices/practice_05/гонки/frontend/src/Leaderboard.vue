<script setup>
import { computed } from "vue";
import { formatTime, nameKey, highlightKey, showLastResultRow } from "./raceLogic.js";

// Таблица рекордов: топ-10 и, если игрока последней гонки в нём нет, отдельная
// строка «Последняя гонка» (specs/contract.md §2.3). Показывается на экранах
// «Выбор» и «Финиш»; данные и загрузку держит App.vue.

const props = defineProps({
  state: { type: String, required: true }, // "loading" | "empty" | "data" | "error"
  board: { type: Object, default: null },
  newRecordKey: { type: String, default: null }, // только на «Финише»
});

const emit = defineEmits(["retry"]);

const highlighted = computed(() => highlightKey(props.board));
const lastResult = computed(() =>
  showLastResultRow(props.board) ? props.board.last_result : null,
);
</script>

<template>
  <section class="leaderboard">
    <h3 class="lb-title">🏆 Рекорды</h3>

    <p v-if="state === 'loading'" class="lb-message">Загрузка рекордов…</p>

    <p v-else-if="state === 'empty'" class="lb-message">Пока нет рекордов — станьте первым!</p>

    <div v-else-if="state === 'error'" class="lb-message lb-error">
      <span>Не удалось загрузить рекорды</span>
      <button class="lb-retry" @click="emit('retry')">Повторить</button>
    </div>

    <table v-else class="lb-table">
      <thead>
        <tr>
          <th class="col-place">Место</th>
          <th class="col-name">Имя</th>
          <th class="col-time">Лучшее время</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="entry in board.entries"
          :key="entry.place"
          :class="{ highlighted: nameKey(entry.name) === highlighted }"
        >
          <td class="col-place">{{ entry.place }}</td>
          <td class="col-name">
            <div class="name-cell">
              <span class="name-text">{{ entry.name }}</span>
              <span v-if="nameKey(entry.name) === newRecordKey" class="new-record">Новый рекорд!</span>
            </div>
          </td>
          <td class="col-time">{{ formatTime(entry.best_time_ms) }}</td>
        </tr>
      </tbody>
      <tbody v-if="lastResult" class="last-result">
        <tr class="last-caption">
          <td colspan="3">Последняя гонка</td>
        </tr>
        <tr>
          <td class="col-place">{{ lastResult.place }}</td>
          <td class="col-name">
            <div class="name-cell">
              <span class="name-text">{{ lastResult.name }}</span>
            </div>
          </td>
          <td class="col-time">{{ formatTime(lastResult.lap_time_ms) }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.leaderboard {
  width: 100%;
  box-sizing: border-box;
  background: rgba(13, 10, 31, 0.6);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 12px;
  padding: 16px;
}

.lb-title {
  margin: 0 0 12px;
  font-size: 1.1rem;
  color: #facc15;
}

.lb-message {
  margin: 0;
  color: #cbd5e1;
}

.lb-error {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
  color: #fca5a5;
}

.lb-retry {
  background: #1a1033;
  color: #22d3ee;
  border: 1px solid #22d3ee;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
}

.lb-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.95rem;
}

.lb-table th {
  color: #22d3ee;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 6px 8px;
  border-bottom: 1px solid rgba(139, 92, 246, 0.3);
}

.lb-table td {
  padding: 6px 8px;
}

.col-place {
  width: 4.5em;
  text-align: center;
}

.col-name {
  text-align: left;
}

/* Длинное имя обрезается многоточием, бейдж при этом остаётся виден */
.name-cell {
  display: flex;
  align-items: center;
  min-width: 0;
}

.col-time {
  width: 7.5em;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.name-text {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

tr.highlighted td {
  background: rgba(34, 211, 238, 0.15);
  color: #22d3ee;
  font-weight: 700;
}

.new-record {
  flex-shrink: 0;
  margin-left: 8px;
  font-size: 0.75rem;
  color: #0d0a1f;
  background: #facc15;
  border-radius: 999px;
  padding: 1px 8px;
  font-weight: 800;
}

.last-result td {
  color: #c084fc;
}

.last-caption td {
  padding-top: 12px;
  border-top: 1px dashed rgba(139, 92, 246, 0.5);
  font-size: 0.75rem;
  text-align: left;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
</style>

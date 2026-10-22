<script setup>
import { ref } from "vue";

// Кнопка "Сообщить об ошибке": открывает маленькую форму, пользователь
// описывает проблему, мы валидируем на фронте (та же логика, что и на
// бэкенде в Фиче A/C) и отправляем на /report-error.

const API_URL = "http://localhost:8000/report-error";
const MAX_LENGTH = 500;

const isOpen = ref(false);
const message = ref("");
const status = ref("idle"); // idle | sending | sent | error
const errorText = ref("");

function open() {
  isOpen.value = true;
  status.value = "idle";
  errorText.value = "";
}

function close() {
  isOpen.value = false;
  message.value = "";
  status.value = "idle";
  errorText.value = "";
}

function validate() {
  const trimmed = message.value.trim();
  if (!trimmed) {
    return "Опиши, что пошло не так — поле не может быть пустым.";
  }
  if (trimmed.length > MAX_LENGTH) {
    return `Слишком длинное сообщение (максимум ${MAX_LENGTH} символов).`;
  }
  return null;
}

async function submit() {
  const validationError = validate();
  if (validationError) {
    errorText.value = validationError;
    return;
  }

  status.value = "sending";
  errorText.value = "";

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message.value.trim() }),
    });

    if (!response.ok) {
      throw new Error("Сервер отклонил сообщение");
    }

    status.value = "sent";
  } catch {
    status.value = "error";
    errorText.value = "Не удалось отправить. Проверь, что бэкенд запущен.";
  }
}
</script>

<template>
  <button class="report-trigger" @click="open" aria-label="Сообщить об ошибке">
    ⚠ Сообщить об ошибке
  </button>

  <div v-if="isOpen" class="report-overlay" @click.self="close">
    <div class="report-panel" role="dialog" aria-modal="true">
      <h2>Сообщить об ошибке</h2>

      <template v-if="status !== 'sent'">
        <textarea
          v-model="message"
          :maxlength="MAX_LENGTH"
          rows="4"
          placeholder="Например: машинка зависла после выбора цвета..."
        />
        <div class="report-meta">
          <span class="report-count">{{ message.length }} / {{ MAX_LENGTH }}</span>
        </div>

        <p v-if="errorText" class="report-error">{{ errorText }}</p>

        <div class="report-actions">
          <button class="btn-secondary" @click="close" :disabled="status === 'sending'">
            Отмена
          </button>
          <button class="btn-primary" @click="submit" :disabled="status === 'sending'">
            {{ status === "sending" ? "Отправка..." : "Отправить" }}
          </button>
        </div>
      </template>

      <template v-else>
        <p class="report-success">Спасибо! Сообщение отправлено на диагностику.</p>
        <div class="report-actions">
          <button class="btn-primary" @click="close">Закрыть</button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.report-trigger {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 50;
  background: #8b5cf6;
  color: #f5f3ff;
  border: none;
  border-radius: 999px;
  padding: 12px 18px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(139, 92, 246, 0.45);
}

.report-trigger:hover {
  background: #7c3aed;
}

.report-overlay {
  position: fixed;
  inset: 0;
  background: rgba(13, 10, 31, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.report-panel {
  background: #1a1033;
  border: 1px solid #8b5cf6;
  border-radius: 12px;
  padding: 24px;
  width: min(420px, 90vw);
  color: #f5f3ff;
}

.report-panel h2 {
  margin: 0 0 12px;
  font-size: 1.1rem;
}

.report-panel textarea {
  width: 100%;
  background: #0d0a1f;
  color: #f5f3ff;
  border: 1px solid #8b5cf6;
  border-radius: 8px;
  padding: 10px;
  resize: vertical;
  font-family: inherit;
}

.report-meta {
  display: flex;
  justify-content: flex-end;
  font-size: 0.8rem;
  color: #c084fc;
  margin-top: 4px;
}

.report-error {
  color: #fca5a5;
  font-size: 0.9rem;
}

.report-success {
  color: #22d3ee;
}

.report-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.btn-primary,
.btn-secondary {
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
  border: none;
  font-weight: 600;
}

.btn-primary {
  background: #22d3ee;
  color: #0d0a1f;
}

.btn-secondary {
  background: transparent;
  color: #f5f3ff;
  border: 1px solid #8b5cf6;
}
</style>

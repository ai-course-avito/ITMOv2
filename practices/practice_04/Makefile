# Makefile-обёртка вокруг CMake (AGENTS.md, раздел 4).
# Все рецепты молчаливые (@): наружу идут только короткие подсказки и вывод
# самих инструментов.

BUILD_DIR := build

# Параметры headless-прогона. Переопределяются из командной строки:
#   make sim SEED=7 SCRIPT=L2CWHOLDHDT30 TICKS=5000
SEED ?= 42
SCRIPT ?= DHOLDHD
TICKS ?= 20000

.PHONY: build test sim run hooks clean help

build:
	@echo "==> Конфигурация и сборка (Release, $(BUILD_DIR)/)"
	@cmake -S . -B $(BUILD_DIR) -DCMAKE_BUILD_TYPE=Release
	@cmake --build $(BUILD_DIR) -j

test: build
	@echo "==> Тесты: ctest --output-on-failure"
	@ctest --test-dir $(BUILD_DIR) --output-on-failure

sim: build
	@echo "==> Симуляция: seed=$(SEED) ticks=$(TICKS) script=\"$(SCRIPT)\""
	@$(BUILD_DIR)/tetris --headless --seed $(SEED) --script "$(SCRIPT)" --ticks $(TICKS)

run: build
	@echo "==> Запуск SDL2-окна (для выхода Esc или Q)"
	@$(BUILD_DIR)/tetris

hooks:
	@echo "==> Хуки проекта: список, здоровье и самопроверка правил"
	@hermes hooks list
	@hermes hooks doctor
	@echo "==> Правила хука frozen_headers на синтетических данных"
	@for cmd in "cat > include/tetris/core/new.hpp" "sed -i s/a/b/ include/tetris/core/types.hpp" "grep -rn X include/tetris/core/types.hpp"; do \
		printf '  %-50s -> ' "$$cmd"; \
		printf '{"tool_name":"terminal","tool_input":{"command":"%s"},"cwd":"%s"}' "$$cmd" "$$(pwd)" \
			| hooks/frozen_headers.py \
			| python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision","пропущено"))'; \
	done

clean:
	@echo "==> Удаление $(BUILD_DIR)/"
	@rm -rf $(BUILD_DIR)

help:
	@echo "Цели практики 4:"
	@echo "  make build                    — cmake -S . -B $(BUILD_DIR) && cmake --build $(BUILD_DIR) -j"
	@echo "  make test                     — ctest --test-dir $(BUILD_DIR) --output-on-failure"
	@echo "  make sim [SEED=42 SCRIPT=DHOLDHD TICKS=20000]"
	@echo "                                — headless-прогон, JSON на stdout"
	@echo "  make run                      — запуск SDL2-окна"
	@echo "  make hooks                    — список и проверка хуков + самопроверка правил"
	@echo "  make clean                    — rm -rf $(BUILD_DIR)"
	@echo "  make help                     — эта справка"

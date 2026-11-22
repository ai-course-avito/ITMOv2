#!/bin/sh
# Единый runner проекта: unit-тесты игровой логики (node:test, без зависимостей).
# Вызывается вручную, из хука после каждой правки и из AGENTS.md.
cd "$(dirname "$0")/.." || exit 2
node --test --test-reporter=dot tests/*.test.js

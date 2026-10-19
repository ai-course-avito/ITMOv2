#!/usr/bin/env bash

set -e

echo "=== Automatic project check ==="
echo "Запуск тестов..."

npm test

echo "Project checks passed."
#!/usr/bin/env bash
# Устанавливает pre-commit hook проекта (git hooks не версионируются сами по себе,
# поэтому каждый разработчик один раз запускает этот скрипт после клонирования).
set -e
REPO_ROOT="$(git rev-parse --show-toplevel)"
cp "$REPO_ROOT/hooks/pre-commit" "$REPO_ROOT/.git/hooks/pre-commit"
chmod +x "$REPO_ROOT/.git/hooks/pre-commit"
echo "✓ pre-commit hook установлен в .git/hooks/pre-commit"

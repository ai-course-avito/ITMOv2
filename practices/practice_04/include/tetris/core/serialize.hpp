// JSON-сериализация состояния игры. Контракт читают тесты, CLI и MCP-сервер:
// ключи менять только вместе с mcp_server/tetris_mcp.py и docs/spec.md.
#pragma once

#include <cstdint>
#include <string>

#include "tetris/core/game.hpp"

namespace tetris {

// Полное состояние в JSON (см. docs/spec.md, раздел 5 — схема ответа).
// include_board=false убирает поле "board" (остаётся board_hash).
std::string to_json(const GameSnapshot& snapshot, bool include_board = true);

// Hex-представление 64-битного хеша (16 символов нижнего регистра).
std::string hash_hex(std::uint64_t value);

}  // namespace tetris

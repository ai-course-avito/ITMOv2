// ASCII-представление состояния. Используется CLI (--ascii) и MCP-инструментом
// tetris_render: агент видит поле, не компилируя UI.
#pragma once

#include <string>

#include "tetris/core/game.hpp"

namespace tetris {

struct AsciiOptions {
    bool with_active{true};   // наложить активную фигуру
    bool with_ghost{true};    // показать призрак символом ':' в клетках призрака
    bool with_frame{true};    // рамка и заголовок
    bool with_stats{true};    // строки счёта/уровня/hold/next
    bool colors{false};       // ANSI-цвета (только для терминала)
};

// Многострочный текст: сверху — верх поля. Активная фигура отображается
// заглавными символами, призрак — ':'. Готов к печати как есть.
std::string render_ascii(const GameSnapshot& snapshot, const AsciiOptions& options = {});

}  // namespace tetris

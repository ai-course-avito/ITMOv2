// SDL2-фронтенд. Ядро о SDL не знает: этот файл только читает снапшоты
// и вызывает Game::apply().
#pragma once

#include "tetris/core/game.hpp"

namespace tetris {

struct SdlConfig {
    int cell_px{28};        // размер клетки в пикселях
    int window_width{0};    // 0 — вычислить из cell_px и размеров поля
    int window_height{0};
    int fps{60};            // частота цикла, совпадает с частотой тиков ядра
    bool show_ghost{true};
};

// Запускает игровой цикл до выхода игрока. Возвращает 0 при нормальном завершении,
// ненулевой код — при ошибке инициализации SDL (текст ошибки идёт в stderr).
int run_sdl(Game& game, const SdlConfig& config = {});

}  // namespace tetris

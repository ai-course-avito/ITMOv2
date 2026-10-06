#pragma once

// Игровое поле 10x20 + четыре невидимые буферные строки сверху.
// y = 0 — нижняя видимая строка, y = 19 — верхняя видимая, y = 20..23 — буфер.
// Буфер из четырёх строк нужен, чтобы вертикальные состояния I (4 клетки в высоту)
// помещались в поле сразу после спавна и поворота.

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "tetris/core/types.hpp"

namespace tetris {

class Board {
public:
    static constexpr int kWidth = 10;
    static constexpr int kVisibleHeight = 20;
    static constexpr int kBufferHeight = 4;
    static constexpr int kHeight = kVisibleHeight + kBufferHeight;  // 24

    static constexpr std::uint8_t kEmpty = 0;

    Board();

    void clear();

    // Свободна ли позиция: все клетки фигуры внутри поля и не заняты.
    bool is_free(const Shape& shape, Point origin) const;

    // Все ли клетки фигуры внутри границ поля (без проверки занятости).
    bool in_bounds(const Shape& shape, Point origin) const;

    // 0 — пусто, иначе 1 + piece_index(type).
    std::uint8_t cell(int x, int y) const;
    void set_cell(int x, int y, std::uint8_t value);

    // Укладывает фигуру на поле. Клетки выше kBufferHeight игнорируются.
    void lock(const Shape& shape, Point origin, PieceType type);

    bool row_full(int y) const;

    // Удаляет заполненные строки, сдвигает верхние вниз. Возвращает число удалённых строк.
    int clear_full_rows();

    // Диагностика: число пустых клеток под занятыми в каждом столбце.
    int count_holes() const;

    // FNV-1a 64 по видимым клеткам поля — для проверки детерминизма.
    std::uint64_t hash() const;

    // ASCII-рендер, строка 0 — верх поля. visible_only=false добавляет буфер.
    std::vector<std::string> to_ascii(bool visible_only = true) const;

    // Позиция спавна фигуры (бокс 4x4, x = 3, нижняя строка бокса в буфере).
    static Point spawn_origin();
    // Позиция появления при hold: тот же столбец, что и у спавна.
    static Point hold_origin();

private:
    std::array<std::array<std::uint8_t, kWidth>, kHeight> cells_{};
};

}  // namespace tetris

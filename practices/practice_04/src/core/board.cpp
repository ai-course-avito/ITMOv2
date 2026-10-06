// Реализация игрового поля (см. board.hpp).
#include "tetris/core/board.hpp"

namespace tetris {

namespace {
// Константы FNV-1a 64.
constexpr std::uint64_t kFnvOffset = 14695981039346656037ULL;
constexpr std::uint64_t kFnvPrime = 1099511628211ULL;
}  // namespace

Board::Board() {
    clear();
}

void Board::clear() {
    for (auto& row : cells_) {
        row.fill(kEmpty);
    }
}

bool Board::in_bounds(const Shape& shape, Point origin) const {
    for (const Point& c : shape) {
        const int x = origin.x + c.x;
        const int y = origin.y + c.y;
        if (x < 0 || x >= kWidth || y < 0 || y >= kHeight) {
            return false;
        }
    }
    return true;
}

bool Board::is_free(const Shape& shape, Point origin) const {
    for (const Point& c : shape) {
        const int x = origin.x + c.x;
        const int y = origin.y + c.y;
        if (x < 0 || x >= kWidth || y < 0 || y >= kHeight) {
            return false;
        }
        if (cells_[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)] != kEmpty) {
            return false;
        }
    }
    return true;
}

std::uint8_t Board::cell(int x, int y) const {
    if (x < 0 || x >= kWidth || y < 0 || y >= kHeight) {
        return kEmpty;
    }
    return cells_[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)];
}

void Board::set_cell(int x, int y, std::uint8_t value) {
    if (x < 0 || x >= kWidth || y < 0 || y >= kHeight) {
        return;
    }
    cells_[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)] = value;
}

void Board::lock(const Shape& shape, Point origin, PieceType type) {
    const std::uint8_t value = static_cast<std::uint8_t>(1 + piece_index(type));
    for (const Point& c : shape) {
        set_cell(origin.x + c.x, origin.y + c.y, value);
    }
}

bool Board::row_full(int y) const {
    if (y < 0 || y >= kHeight) {
        return false;
    }
    for (int x = 0; x < kWidth; ++x) {
        if (cells_[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)] == kEmpty) {
            return false;
        }
    }
    return true;
}

int Board::clear_full_rows() {
    // Идём снизу вверх; выжившие строки сдвигаются вниз (в начало массива).
    int removed = 0;
    int write = 0;
    for (int y = 0; y < kHeight; ++y) {
        if (row_full(y)) {
            ++removed;
            continue;
        }
        if (write != y) {
            cells_[static_cast<std::size_t>(write)] = cells_[static_cast<std::size_t>(y)];
        }
        ++write;
    }
    for (int y = write; y < kHeight; ++y) {
        cells_[static_cast<std::size_t>(y)].fill(kEmpty);
    }
    return removed;
}

int Board::count_holes() const {
    // Дырка — пустая клетка под первой (сверху) занятой клеткой столбца.
    int holes = 0;
    for (int x = 0; x < kWidth; ++x) {
        bool seen_block = false;
        for (int y = kVisibleHeight - 1; y >= 0; --y) {
            if (cells_[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)] != kEmpty) {
                seen_block = true;
            } else if (seen_block) {
                ++holes;
            }
        }
    }
    return holes;
}

std::uint64_t Board::hash() const {
    // FNV-1a 64 только по видимым клеткам (буфер не влияет на хеш).
    std::uint64_t h = kFnvOffset;
    for (int y = 0; y < kVisibleHeight; ++y) {
        for (int x = 0; x < kWidth; ++x) {
            h ^= static_cast<std::uint64_t>(
                cells_[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)]);
            h *= kFnvPrime;
        }
    }
    return h;
}

std::vector<std::string> Board::to_ascii(bool visible_only) const {
    std::vector<std::string> out;
    const int top = visible_only ? kVisibleHeight - 1 : kHeight - 1;
    for (int y = top; y >= 0; --y) {
        std::string line;
        line.reserve(static_cast<std::size_t>(kWidth));
        for (int x = 0; x < kWidth; ++x) {
            const std::uint8_t v = cells_[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)];
            if (v == kEmpty) {
                line.push_back('.');
            } else {
                line.push_back(piece_char(static_cast<PieceType>(v - 1)));
            }
        }
        out.push_back(std::move(line));
    }
    return out;
}

Point Board::spawn_origin() {
    // Бокс 4x4 прижат к столбцу x = 3, нижняя строка бокса лежит на y = 20.
    return Point{3, kVisibleHeight};
}

Point Board::hold_origin() {
    return spawn_origin();
}

}  // namespace tetris

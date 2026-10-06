// Базовые типы ядра Tetris. Заголовок — часть замороженного интерфейса:
// сигнатуры меняет только архитектор (см. AGENTS.md).
#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace tetris {

// Порядок фиксирован: он же используется как значение клетки на поле (1 + PieceType).
enum class PieceType : std::uint8_t { I = 0, J, L, O, S, T, Z };
constexpr int kPieceTypeCount = 7;

inline int piece_index(PieceType t) { return static_cast<int>(t); }

// Состояния поворота SRS: 0 = спавн, 1 = R (по часовой), 2 = два оборота, 3 = L.
enum class Rotation : std::uint8_t { Spawn = 0, Right = 1, Two = 2, Left = 3 };

inline Rotation rotate_cw(Rotation r) { return static_cast<Rotation>((static_cast<int>(r) + 1) % 4); }
inline Rotation rotate_ccw(Rotation r) { return static_cast<Rotation>((static_cast<int>(r) + 3) % 4); }

struct Point {
    int x{0};
    int y{0};
};

inline bool operator==(const Point& a, const Point& b) { return a.x == b.x && a.y == b.y; }
inline bool operator!=(const Point& a, const Point& b) { return !(a == b); }

// Четыре занятые клетки внутри бокса 4x4. Координаты бокса: x вправо, y вверх,
// (0,0) — нижний левый угол бокса. Фигуры занимают только нижние две строки бокса,
// поэтому спавн целиком попадает в буферные строки поля.
using Shape = std::array<Point, 4>;

// Символ фигуры для ASCII-рендера и протокола MCP ('I','J','L','O','S','T','Z').
char piece_char(PieceType t);
const char* piece_name(PieceType t);

// Разбор символа фигуры; для неизвестного символа возвращает std::nullopt.
std::optional<PieceType> piece_from_char(char c);

}  // namespace tetris

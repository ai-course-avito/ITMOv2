// Явные таблицы форм фигур по состояниям поворота и таблицы вылетов SRS.
//
// Формы закодированы покомпонентно (не выводятся формулой в рантайме), чтобы
// таблицу можно было сверить построчно со спецификацией (docs/spec.md, раздел 2).
// Координаты — в боксе 4x4, y направлен вверх, (0,0) — нижний левый угол бокса.
#include "tetris/core/pieces.hpp"

#include <array>

namespace tetris {

namespace {

// Форма одного состояния поворота: четыре занятые клетки бокса.
using StateShapes = std::array<Shape, 4>;

// Спавн, Right, Two, Left — в порядке Rotation (0,1,2,3).
constexpr StateShapes kShapesI{{
    Shape{{Point{0, 1}, Point{1, 1}, Point{2, 1}, Point{3, 1}}},
    Shape{{Point{2, 0}, Point{2, 1}, Point{2, 2}, Point{2, 3}}},
    Shape{{Point{0, 2}, Point{1, 2}, Point{2, 2}, Point{3, 2}}},
    Shape{{Point{1, 0}, Point{1, 1}, Point{1, 2}, Point{1, 3}}},
}};

constexpr StateShapes kShapesJ{{
    Shape{{Point{0, 0}, Point{1, 0}, Point{2, 0}, Point{0, 1}}},
    Shape{{Point{0, 0}, Point{0, 1}, Point{0, 2}, Point{1, 2}}},
    Shape{{Point{0, 2}, Point{2, 1}, Point{1, 2}, Point{2, 2}}},
    Shape{{Point{1, 0}, Point{2, 0}, Point{2, 1}, Point{2, 2}}},
}};

constexpr StateShapes kShapesL{{
    Shape{{Point{0, 0}, Point{1, 0}, Point{2, 0}, Point{2, 1}}},
    Shape{{Point{0, 0}, Point{0, 1}, Point{0, 2}, Point{1, 0}}},
    Shape{{Point{0, 1}, Point{0, 2}, Point{1, 2}, Point{2, 2}}},
    Shape{{Point{1, 2}, Point{2, 0}, Point{2, 1}, Point{2, 2}}},
}};

// O при любом повороте занимает один и тот же квадрат 2x2.
constexpr StateShapes kShapesO{{
    Shape{{Point{1, 0}, Point{1, 1}, Point{2, 0}, Point{2, 1}}},
    Shape{{Point{1, 0}, Point{1, 1}, Point{2, 0}, Point{2, 1}}},
    Shape{{Point{1, 0}, Point{1, 1}, Point{2, 0}, Point{2, 1}}},
    Shape{{Point{1, 0}, Point{1, 1}, Point{2, 0}, Point{2, 1}}},
}};

constexpr StateShapes kShapesS{{
    Shape{{Point{0, 0}, Point{1, 0}, Point{1, 1}, Point{2, 1}}},
    Shape{{Point{0, 1}, Point{0, 2}, Point{1, 0}, Point{1, 1}}},
    Shape{{Point{0, 1}, Point{1, 1}, Point{1, 2}, Point{2, 2}}},
    Shape{{Point{1, 1}, Point{1, 2}, Point{2, 0}, Point{2, 1}}},
}};

constexpr StateShapes kShapesT{{
    Shape{{Point{0, 0}, Point{1, 0}, Point{1, 1}, Point{2, 0}}},
    Shape{{Point{0, 0}, Point{0, 1}, Point{0, 2}, Point{1, 1}}},
    Shape{{Point{0, 2}, Point{1, 1}, Point{1, 2}, Point{2, 2}}},
    Shape{{Point{1, 1}, Point{2, 0}, Point{2, 1}, Point{2, 2}}},
}};

constexpr StateShapes kShapesZ{{
    Shape{{Point{0, 1}, Point{1, 0}, Point{1, 1}, Point{2, 0}}},
    Shape{{Point{0, 0}, Point{0, 1}, Point{1, 1}, Point{1, 2}}},
    Shape{{Point{0, 2}, Point{1, 1}, Point{1, 2}, Point{2, 1}}},
    Shape{{Point{1, 0}, Point{1, 1}, Point{2, 1}, Point{2, 2}}},
}};

constexpr std::array<StateShapes, kPieceTypeCount> kShapes{
    kShapesI, kShapesJ, kShapesL, kShapesO, kShapesS, kShapesT, kShapesZ,
};

// Последовательности вылетов SRS. Смещения в порядке перебора: сначала (0,0),
// затем остальные четыре (docs/spec.md, раздел 2, «Вылеты SRS»).
const std::vector<Point> kKickA{{0, 0}, {-1, 0}, {-1, 1}, {0, -2}, {-1, -2}};
const std::vector<Point> kKickB{{0, 0}, {1, 0}, {1, -1}, {0, 2}, {1, 2}};
const std::vector<Point> kKickC{{0, 0}, {1, 0}, {1, 1}, {0, -2}, {1, -2}};
const std::vector<Point> kKickD{{0, 0}, {-1, 0}, {-1, -1}, {0, 2}, {-1, 2}};

const std::vector<Point> kKickI0R{{0, 0}, {-2, 0}, {1, 0}, {-2, -1}, {1, 2}};
const std::vector<Point> kKickIR0{{0, 0}, {2, 0}, {-1, 0}, {2, 1}, {-1, -2}};
const std::vector<Point> kKickIR2{{0, 0}, {-1, 0}, {2, 0}, {-1, 2}, {2, -1}};
const std::vector<Point> kKickI2R{{0, 0}, {1, 0}, {-2, 0}, {1, -2}, {-2, 1}};

// O вращается всегда без смещений.
const std::vector<Point> kKickNone{};

// Переход для JLSTZ: четыре различные последовательности A/B/C/D.
const std::vector<Point>& jlstz_kick(Rotation from, Rotation to) {
    const int f = static_cast<int>(from);
    const int t = static_cast<int>(to);
    if (f == 0 && t == 1) return kKickA;  // 0 -> R
    if (f == 1 && t == 0) return kKickB;  // R -> 0
    if (f == 1 && t == 2) return kKickB;  // R -> 2
    if (f == 2 && t == 1) return kKickA;  // 2 -> R
    if (f == 2 && t == 3) return kKickC;  // 2 -> L
    if (f == 3 && t == 2) return kKickD;  // L -> 2
    if (f == 3 && t == 0) return kKickC;  // L -> 0
    if (f == 0 && t == 3) return kKickD;  // 0 -> L
    return kKickNone;
}

const std::vector<Point>& i_kick(Rotation from, Rotation to) {
    const int f = static_cast<int>(from);
    const int t = static_cast<int>(to);
    if (f == 0 && t == 1) return kKickI0R;
    if (f == 1 && t == 0) return kKickIR0;
    if (f == 1 && t == 2) return kKickIR2;
    if (f == 2 && t == 1) return kKickI2R;
    if (f == 2 && t == 3) return kKickIR0;  // 2 -> L использует набор R -> 0
    if (f == 3 && t == 2) return kKickI0R;  // L -> 2 использует набор 0 -> R
    if (f == 3 && t == 0) return kKickI2R;  // L -> 0 использует набор 2 -> R
    if (f == 0 && t == 3) return kKickIR2;  // 0 -> L использует набор R -> 2
    return kKickNone;
}

}  // namespace

Shape piece_shape(PieceType t, Rotation r) {
    const int ti = piece_index(t);
    const int ri = static_cast<int>(r) & 3;
    return kShapes[static_cast<std::size_t>(ti)][static_cast<std::size_t>(ri)];
}

const std::vector<Point>& srs_kicks(PieceType t, Rotation from, Rotation to) {
    if (t == PieceType::O) return kKickNone;
    if (t == PieceType::I) return i_kick(from, to);
    return jlstz_kick(from, to);
}

}  // namespace tetris

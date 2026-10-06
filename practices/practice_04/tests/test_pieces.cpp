// Тесты форм фигур и таблиц вылетов SRS (docs/spec.md, раздел 8, п.2).
#include "tetris/core/pieces.hpp"

#include "test_framework.hpp"

#include <algorithm>
#include <array>
#include <initializer_list>
#include <set>
#include <vector>

using namespace tetris;

namespace {

bool contains(const Shape& shape, Point p) {
    for (const Point& c : shape) {
        if (c == p) return true;
    }
    return false;
}

bool same_shape(const Shape& a, const Shape& b) {
    for (const Point& c : a) {
        if (!contains(b, c)) return false;
    }
    for (const Point& c : b) {
        if (!contains(a, c)) return false;
    }
    return true;
}

Shape make_shape(std::initializer_list<Point> cells) {
    Shape s{};
    std::size_t i = 0;
    for (const Point& p : cells) {
        s[i++] = p;
    }
    return s;
}

bool eq_kick(const std::vector<Point>& got, const std::vector<Point>& exp) {
    if (got.size() != exp.size()) return false;
    for (std::size_t i = 0; i < got.size(); ++i) {
        if (got[i] != exp[i]) return false;
    }
    return true;
}

const std::array<PieceType, 7> kAllTypes{PieceType::I, PieceType::J, PieceType::L, PieceType::O,
                                         PieceType::S, PieceType::T, PieceType::Z};

}  // namespace

TEST(pieces, every_rotation_has_four_distinct_cells) {
    for (PieceType t : kAllTypes) {
        for (int r = 0; r < 4; ++r) {
            const Shape shape = piece_shape(t, static_cast<Rotation>(r));
            std::set<int> unique;
            for (const Point& c : shape) {
                CHECK(c.x >= 0 && c.x < 4);
                CHECK(c.y >= 0 && c.y < 4);
                unique.insert(c.x * 10 + c.y);
            }
            CHECK_EQ(static_cast<int>(unique.size()), 4);
        }
    }
}

TEST(pieces, t_spawn_points_up) {
    const Shape expected = make_shape({{0, 0}, {1, 0}, {2, 0}, {1, 1}});
    CHECK(same_shape(piece_shape(PieceType::T, Rotation::Spawn), expected));
}

TEST(pieces, t_right_is_vertical_with_nose_on_the_right) {
    const Shape expected = make_shape({{0, 0}, {0, 1}, {0, 2}, {1, 1}});
    CHECK(same_shape(piece_shape(PieceType::T, Rotation::Right), expected));
    // Вертикальная стойка: три клетки в столбце x = 0, «нос» смотрит вправо.
    const Shape shape = piece_shape(PieceType::T, Rotation::Right);
    int in_column = 0;
    for (const Point& c : shape) {
        if (c.x == 0) ++in_column;
    }
    CHECK_EQ(in_column, 3);
    CHECK((contains(shape, Point{1, 1})));
}

TEST(pieces, i_right_is_vertical_line_of_four) {
    const Shape expected = make_shape({{2, 0}, {2, 1}, {2, 2}, {2, 3}});
    CHECK(same_shape(piece_shape(PieceType::I, Rotation::Right), expected));
    const Shape shape = piece_shape(PieceType::I, Rotation::Right);
    for (const Point& c : shape) {
        CHECK_EQ(c.x, 2);
    }
}

TEST(pieces, i_states_match_rotation_formula) {
    CHECK(same_shape(piece_shape(PieceType::I, Rotation::Two),
                     make_shape({{0, 2}, {1, 2}, {2, 2}, {3, 2}})));
    CHECK(same_shape(piece_shape(PieceType::I, Rotation::Left),
                     make_shape({{1, 0}, {1, 1}, {1, 2}, {1, 3}})));
}

TEST(pieces, o_does_not_change_with_rotation) {
    const Shape spawn = piece_shape(PieceType::O, Rotation::Spawn);
    for (int r = 1; r < 4; ++r) {
        CHECK(same_shape(piece_shape(PieceType::O, static_cast<Rotation>(r)), spawn));
    }
}

TEST(pieces, s_and_z_180_states_are_translated) {
    // Поворот на 180° даёт ту же форму, сдвинутую в боксе на одну строку вверх.
    const Shape s0 = piece_shape(PieceType::S, Rotation::Spawn);
    const Shape s2 = piece_shape(PieceType::S, Rotation::Two);
    for (const Point& c : s0) {
        CHECK(contains(s2, Point{c.x, c.y + 1}));
    }
    const Shape z0 = piece_shape(PieceType::Z, Rotation::Spawn);
    const Shape z2 = piece_shape(PieceType::Z, Rotation::Two);
    for (const Point& c : z0) {
        CHECK(contains(z2, Point{c.x, c.y + 1}));
    }
}

TEST(pieces, rotation_state_counts_are_correct) {
    // O не меняется; S и Z симметричны относительно 180°; остальные дают 4 формы.
    const auto distinct = [](PieceType t) {
        std::set<int> shapes;
        for (int r = 0; r < 4; ++r) {
            const Shape shape = piece_shape(t, static_cast<Rotation>(r));
            // Собираем устойчивый идентификатор множества клеток.
            std::array<Point, 4> sorted = shape;
            std::sort(sorted.begin(), sorted.end(),
                      [](Point a, Point b) { return a.x != b.x ? a.x < b.x : a.y < b.y; });
            int code = 0;
            for (const Point& c : sorted) code = code * 100 + c.x * 10 + c.y;
            shapes.insert(code);
        }
        return static_cast<int>(shapes.size());
    };
    CHECK_EQ(distinct(PieceType::I), 4);
    CHECK_EQ(distinct(PieceType::J), 4);
    CHECK_EQ(distinct(PieceType::L), 4);
    CHECK_EQ(distinct(PieceType::T), 4);
    CHECK_EQ(distinct(PieceType::O), 1);
    CHECK_EQ(distinct(PieceType::S), 4);
    CHECK_EQ(distinct(PieceType::Z), 4);
}

TEST(pieces, kicks_present_for_jlstz_and_i_absent_for_o) {
    const Rotation order[4] = {Rotation::Spawn, Rotation::Right, Rotation::Two, Rotation::Left};
    for (PieceType t : kAllTypes) {
        for (int i = 0; i < 4; ++i) {
            const Rotation from = order[i];
            const Rotation cw_to = order[(i + 1) % 4];
            const Rotation ccw_to = order[(i + 3) % 4];
            for (Rotation to : {cw_to, ccw_to}) {
                const std::vector<Point>& kicks = srs_kicks(t, from, to);
                if (t == PieceType::O) {
                    CHECK(kicks.empty());
                } else {
                    CHECK_EQ(kicks.size(), static_cast<std::size_t>(5));
                    CHECK((kicks.front() == Point{0, 0}));
                }
            }
        }
    }
}

TEST(pieces, jlstz_kick_tables_match_specification) {
    const std::vector<Point> a{{0, 0}, {-1, 0}, {-1, 1}, {0, -2}, {-1, -2}};
    const std::vector<Point> b{{0, 0}, {1, 0}, {1, -1}, {0, 2}, {1, 2}};
    const std::vector<Point> c{{0, 0}, {1, 0}, {1, 1}, {0, -2}, {1, -2}};
    const std::vector<Point> d{{0, 0}, {-1, 0}, {-1, -1}, {0, 2}, {-1, 2}};
    CHECK(eq_kick(srs_kicks(PieceType::T, Rotation::Spawn, Rotation::Right), a));
    CHECK(eq_kick(srs_kicks(PieceType::T, Rotation::Right, Rotation::Spawn), b));
    CHECK(eq_kick(srs_kicks(PieceType::T, Rotation::Right, Rotation::Two), b));
    CHECK(eq_kick(srs_kicks(PieceType::T, Rotation::Two, Rotation::Right), a));
    CHECK(eq_kick(srs_kicks(PieceType::T, Rotation::Two, Rotation::Left), c));
    CHECK(eq_kick(srs_kicks(PieceType::T, Rotation::Left, Rotation::Two), d));
    CHECK(eq_kick(srs_kicks(PieceType::T, Rotation::Left, Rotation::Spawn), c));
    CHECK(eq_kick(srs_kicks(PieceType::T, Rotation::Spawn, Rotation::Left), d));
    // Все JLSTZ-фигуры пользуются одной таблицей.
    CHECK(eq_kick(srs_kicks(PieceType::J, Rotation::Spawn, Rotation::Right), a));
    CHECK(eq_kick(srs_kicks(PieceType::L, Rotation::Two, Rotation::Left), c));
    CHECK(eq_kick(srs_kicks(PieceType::S, Rotation::Left, Rotation::Spawn), c));
    CHECK(eq_kick(srs_kicks(PieceType::Z, Rotation::Spawn, Rotation::Left), d));
}

TEST(pieces, i_kick_tables_match_specification) {
    const std::vector<Point> i0r{{0, 0}, {-2, 0}, {1, 0}, {-2, -1}, {1, 2}};
    const std::vector<Point> ir0{{0, 0}, {2, 0}, {-1, 0}, {2, 1}, {-1, -2}};
    const std::vector<Point> ir2{{0, 0}, {-1, 0}, {2, 0}, {-1, 2}, {2, -1}};
    const std::vector<Point> i2r{{0, 0}, {1, 0}, {-2, 0}, {1, -2}, {-2, 1}};
    CHECK(eq_kick(srs_kicks(PieceType::I, Rotation::Spawn, Rotation::Right), i0r));
    CHECK(eq_kick(srs_kicks(PieceType::I, Rotation::Left, Rotation::Two), i0r));
    CHECK(eq_kick(srs_kicks(PieceType::I, Rotation::Right, Rotation::Spawn), ir0));
    CHECK(eq_kick(srs_kicks(PieceType::I, Rotation::Two, Rotation::Left), ir0));
    CHECK(eq_kick(srs_kicks(PieceType::I, Rotation::Right, Rotation::Two), ir2));
    CHECK(eq_kick(srs_kicks(PieceType::I, Rotation::Spawn, Rotation::Left), ir2));
    CHECK(eq_kick(srs_kicks(PieceType::I, Rotation::Two, Rotation::Right), i2r));
    CHECK(eq_kick(srs_kicks(PieceType::I, Rotation::Left, Rotation::Spawn), i2r));
}

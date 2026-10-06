// Тесты игрового поля (docs/spec.md, раздел 8, п.3).
#include "tetris/core/board.hpp"
#include "tetris/core/pieces.hpp"

#include "test_framework.hpp"

#include <string>
#include <vector>

using namespace tetris;

namespace {

int filled_visible(const Board& b) {
    int n = 0;
    for (int y = 0; y < Board::kVisibleHeight; ++y) {
        for (int x = 0; x < Board::kWidth; ++x) {
            if (b.cell(x, y) != Board::kEmpty) ++n;
        }
    }
    return n;
}

}  // namespace

TEST(board, new_board_is_empty) {
    Board b;
    CHECK_EQ(static_cast<int>(b.cell(0, 0)), 0);
    CHECK_EQ(static_cast<int>(b.cell(9, 19)), 0);
    CHECK_EQ(b.count_holes(), 0);
    CHECK_EQ(filled_visible(b), 0);
}

TEST(board, dimensions_and_spawn_origins) {
    CHECK_EQ(Board::kWidth, 10);
    CHECK_EQ(Board::kVisibleHeight, 20);
    CHECK_EQ(Board::kBufferHeight, 4);
    CHECK_EQ(Board::kHeight, 24);
    CHECK((Board::spawn_origin() == Point{3, 20}));
    CHECK((Board::hold_origin() == Point{3, 20}));
}

TEST(board, bounds_check_rejects_out_of_field) {
    Board b;
    const Shape shape = piece_shape(PieceType::I, Rotation::Right);  // столбец x = 2
    CHECK((b.in_bounds(shape, Point{8, 0}) == false));   // x = 10 — за правой границей
    CHECK((b.in_bounds(shape, Point{7, 0}) == true));
    CHECK((b.in_bounds(shape, Point{0, -1}) == false));  // y = -1 — под полом
    CHECK((b.is_free(shape, Point{8, 0}) == false));
}

TEST(board, collision_with_locked_cells) {
    Board b;
    b.set_cell(0, 0, 1);
    const Shape t = piece_shape(PieceType::T, Rotation::Spawn);  // клетка (0,0) внутри формы
    CHECK((b.is_free(t, Point{0, 0}) == false));
    CHECK((b.is_free(t, Point{1, 0}) == true));
    // После освобождения клетки позиция снова свободна.
    b.set_cell(0, 0, Board::kEmpty);
    CHECK((b.is_free(t, Point{0, 0}) == true));
}

TEST(board, cell_roundtrip_and_type_value) {
    Board b;
    b.lock(piece_shape(PieceType::L, Rotation::Spawn), Point{0, 0}, PieceType::L);
    const std::uint8_t v = b.cell(2, 0);
    CHECK_EQ(static_cast<int>(v), 1 + piece_index(PieceType::L));
    CHECK_EQ(piece_char(static_cast<PieceType>(v - 1)), 'L');
}

TEST(board, clear_full_rows_shifts_columns_down) {
    Board b;
    // Полная нижняя строка плюс одна клетка над ней.
    for (int x = 0; x < Board::kWidth; ++x) b.set_cell(x, 0, 1);
    b.set_cell(2, 1, 1);
    CHECK(b.row_full(0));
    const int removed = b.clear_full_rows();
    CHECK_EQ(removed, 1);
    CHECK_EQ(static_cast<int>(b.cell(2, 0)), 1);  // клетка съехала вниз
    CHECK_EQ(static_cast<int>(b.cell(2, 1)), 0);
    CHECK_EQ(filled_visible(b), 1);
}

TEST(board, clear_full_rows_handles_multiple_rows) {
    Board b;
    for (int y = 0; y < 3; ++y) {
        for (int x = 0; x < Board::kWidth; ++x) b.set_cell(x, y, 1);
    }
    b.set_cell(5, 3, 2);
    const int removed = b.clear_full_rows();
    CHECK_EQ(removed, 3);
    CHECK_EQ(static_cast<int>(b.cell(5, 0)), 2);
    CHECK_EQ(filled_visible(b), 1);
}

TEST(board, count_holes_counts_empty_cells_below_blocks) {
    Board b;
    b.set_cell(0, 5, 1);  // под блоками y = 0..4 пусто → 5 дырок
    CHECK_EQ(b.count_holes(), 5);
    b.set_cell(1, 2, 1);
    CHECK_EQ(b.count_holes(), 5 + 2);
}

TEST(board, hash_is_stable_and_uses_visible_cells_only) {
    Board a;
    Board b;
    a.set_cell(3, 7, 1);
    b.set_cell(3, 7, 1);
    CHECK_EQ(a.hash(), b.hash());
    a.set_cell(4, 7, 1);
    CHECK(a.hash() != b.hash());
    // Буферные строки не входят в хеш.
    const std::uint64_t before = b.hash();
    b.set_cell(0, 23, 5);
    CHECK_EQ(b.hash(), before);
    // Видимая клетка хеш меняет.
    b.set_cell(0, 19, 5);
    CHECK(b.hash() != before);
}

TEST(board, to_ascii_is_twenty_rows_top_down) {
    Board b;
    b.set_cell(0, 0, 1 + piece_index(PieceType::Z));  // нижняя левая клетка
    const std::vector<std::string> rows = b.to_ascii(true);
    CHECK_EQ(rows.size(), static_cast<std::size_t>(20));
    for (const std::string& row : rows) {
        CHECK_EQ(row.size(), static_cast<std::size_t>(10));
    }
    CHECK_EQ(rows[0], std::string(".........."));     // строка 0 — верх (y = 19)
    CHECK_EQ(rows[19], std::string("Z........."));    // последняя строка — низ (y = 0)
}

TEST(board, to_ascii_can_include_buffer) {
    Board b;
    const std::vector<std::string> rows = b.to_ascii(false);
    CHECK_EQ(rows.size(), static_cast<std::size_t>(24));
}

TEST(board, lock_ignores_cells_outside_field) {
    Board b;
    // Фигура, у которой часть клеток выше поля, не должна падать/писать вне массива.
    const Shape t = piece_shape(PieceType::O, Rotation::Spawn);
    b.lock(t, Point{3, 23}, PieceType::O);  // клетки на y = 23 и 24 → вторая игнорируется
    CHECK_EQ(static_cast<int>(b.cell(4, 23)), 1 + piece_index(PieceType::O));
}

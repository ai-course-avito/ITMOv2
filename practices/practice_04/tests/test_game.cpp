// Тесты ядра игры (docs/spec.md, раздел 8, п.5).
#include "tetris/core/game.hpp"

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

bool has_event(const GameSnapshot& s, const std::string& name) {
    for (const std::string& e : s.events) {
        if (e == name) return true;
    }
    return false;
}

}  // namespace

TEST(game, spawns_first_piece_in_buffer) {
    Game g(5);  // seed 5: первая фигура мешка — I
    const GameSnapshot s = g.snapshot();
    REQUIRE(s.active.has_value());
    CHECK(s.active->type == PieceType::I);
    CHECK(s.active->rotation == Rotation::Spawn);
    CHECK((s.active->pos == Point{3, 20}));
    CHECK_EQ(s.tick, static_cast<std::uint64_t>(0));
}

TEST(game, next_queue_has_five_pieces) {
    Game g(1);
    const GameSnapshot s = g.snapshot();
    CHECK_EQ(s.next.size(), static_cast<std::size_t>(kNextQueueSize));
}

TEST(game, gravity_moves_one_row_per_frames) {
    Game g(1);  // первая фигура O
    g.advance_ticks(47);
    const GameSnapshot s47 = g.snapshot();
    CHECK_EQ(s47.active->pos.y, 20);
    CHECK_EQ(s47.tick, static_cast<std::uint64_t>(47));
    g.advance_ticks(1);
    const GameSnapshot s48 = g.snapshot();
    CHECK_EQ(s48.active->pos.y, 19);
    CHECK_EQ(s48.tick, static_cast<std::uint64_t>(48));
}

TEST(game, moves_respect_walls) {
    Game g(5);  // I: горизонтальная линия из четырёх клеток
    for (int i = 0; i < 6; ++i) g.apply(Action::Left);
    const GameSnapshot left = g.snapshot();
    CHECK_EQ(left.active->pos.x, 0);  // дальше некуда
    CHECK_FALSE(g.apply(Action::Left));
    for (int i = 0; i < 12; ++i) g.apply(Action::Right);
    const GameSnapshot right = g.snapshot();
    CHECK_EQ(right.active->pos.x, 6);
    CHECK_FALSE(g.apply(Action::Right));
}

TEST(game, rotate_cw_changes_state_and_shape) {
    Game g(42);  // первая фигура T
    CHECK(g.snapshot().active->type == PieceType::T);
    const bool ok = g.apply(Action::RotateCW);
    CHECK(ok);
    const GameSnapshot s = g.snapshot();
    CHECK(s.active->rotation == Rotation::Right);
    for (int i = 0; i < 4; ++i) {
        CHECK(s.active->shape[static_cast<std::size_t>(i)] ==
              piece_shape(PieceType::T, Rotation::Right)[static_cast<std::size_t>(i)]);
    }
}

TEST(game, srs_wall_kick_moves_piece_off_the_wall) {
    // I у левой стены: поворот из вертикали в горизонталь возможен только с вылетом.
    Game g(5);
    g.apply(Action::RotateCW);  // I -> вертикальный столбец x = 5
    for (int i = 0; i < 5; ++i) g.apply(Action::Left);
    {
        const GameSnapshot s = g.snapshot();
        CHECK(s.active->rotation == Rotation::Right);
        CHECK_EQ(s.active->pos.x, -2);
    }
    g.apply(Action::Right);
    const GameSnapshot before = g.snapshot();
    CHECK_EQ(before.active->pos.x, -1);
    const bool ok = g.apply(Action::RotateCCW);  // Right -> Spawn
    CHECK(ok);
    const GameSnapshot s = g.snapshot();
    CHECK(s.active->rotation == Rotation::Spawn);
    // Смещение (0,0) дало бы x = -1 (за границей); вылет ставит фигуру в x = 1.
    CHECK_EQ(s.active->pos.x, 1);
}

TEST(game, hold_swaps_once_per_piece) {
    Game g(1);  // первая фигура O, следующая J
    const PieceType first = g.snapshot().active->type;
    const bool ok = g.apply(Action::Hold);
    CHECK(ok);
    const GameSnapshot s = g.snapshot();
    REQUIRE(s.hold.has_value());
    CHECK(*s.hold == first);
    CHECK(s.hold_used);
    CHECK(s.active->type == PieceType::J);
    CHECK(s.active->pos == Board::hold_origin());
    // Второй hold для той же фигуры недоступен.
    CHECK_FALSE(g.apply(Action::Hold));
    CHECK(g.snapshot().hold_used);
}

TEST(game, hold_swap_returns_piece_from_hold) {
    Game g(1);
    const PieceType first = g.snapshot().active->type;
    g.apply(Action::Hold);       // O -> hold, активная J
    g.apply(Action::HardDrop);   // J уложена, hold сброшен
    CHECK_FALSE(g.snapshot().hold_used);
    const bool ok = g.apply(Action::Hold);  // берём O обратно
    CHECK(ok);
    CHECK(g.snapshot().active->type == first);
}

TEST(game, hard_drop_locks_piece_immediately) {
    Game g(5);  // I
    CHECK_EQ(filled_visible(g.snapshot().board), 0);
    const bool ok = g.apply(Action::HardDrop);
    CHECK(ok);
    const GameSnapshot s = g.snapshot();
    CHECK_EQ(filled_visible(s.board), 4);  // линия I уложена на дно
    CHECK(s.active.has_value());
    CHECK(s.active->type == PieceType::T);  // следующая фигура из мешка
    CHECK(has_event(s, "hard_drop"));
}

TEST(game, lock_delay_locks_after_thirty_ticks) {
    Game g(5);  // I
    for (int i = 0; i < 25; ++i) g.apply(Action::SoftDrop);  // I ложится на дно
    CHECK_EQ(filled_visible(g.snapshot().board), 0);
    CHECK(g.snapshot().active->type == PieceType::I);
    g.advance_ticks(29);
    CHECK_EQ(filled_visible(g.snapshot().board), 0);
    CHECK(g.snapshot().active->type == PieceType::I);
    g.advance_ticks(1);
    CHECK_EQ(filled_visible(g.snapshot().board), 4);
    CHECK(g.snapshot().active->type == PieceType::T);
}

TEST(game, lock_delay_resets_on_successful_move) {
    Game g(5);
    for (int i = 0; i < 25; ++i) g.apply(Action::SoftDrop);
    g.advance_ticks(20);
    CHECK(g.apply(Action::Left));  // удачный сдвиг сбрасывает таймер
    g.advance_ticks(25);           // 20 + 25 = 45 тиков без сброса хватило бы для замка
    const GameSnapshot s = g.snapshot();
    REQUIRE(s.active.has_value());
    CHECK(s.active->type == PieceType::I);  // фигура ещё не уложена
    CHECK_EQ(s.active->pos.x, 2);
}

TEST(game, soft_drop_scores_one_point_per_cell) {
    Game g(5);
    const int moved = 5;
    for (int i = 0; i < moved; ++i) g.apply(Action::SoftDrop);
    const GameSnapshot s = g.snapshot();
    CHECK_EQ(s.score, static_cast<long long>(moved));
}

TEST(game, tspin_full_is_detected) {
    // Сценарий с вращением T в углу: фиксируем full T-spin без очистки строк.
    const GameSnapshot s = run_script(3, "HD HD CW CW HD", 20000);
    CHECK(has_event(s, "clear:tspin"));
    CHECK_EQ(s.score, static_cast<long long>(512));
    CHECK(s.back_to_back);  // T-spin — сложная очистка
}

TEST(game, tspin_mini_is_detected) {
    const GameSnapshot s = run_script(3, "HD HD CCW HD", 20000);
    CHECK(has_event(s, "clear:tspin_mini"));
    CHECK_EQ(s.score, static_cast<long long>(210));
}

TEST(game, block_out_sets_game_over) {
    std::string script;
    for (int i = 0; i < 40; ++i) script += "HD ";
    const GameSnapshot s = run_script(42, script, 20000);
    CHECK(s.game_over);
    CHECK(has_event(s, "game_over"));
}

TEST(game, deterministic_two_runs_share_hash_and_score) {
    const std::string script = "L L D HD R CW HD HOLD HD";
    const GameSnapshot a = run_script(42, script, 20000);
    const GameSnapshot b = run_script(42, script, 20000);
    CHECK_EQ(a.board.hash(), b.board.hash());
    CHECK_EQ(a.score, b.score);
    CHECK_EQ(a.lines, b.lines);
    CHECK_EQ(a.tick, b.tick);
}

TEST(game, advance_ticks_matches_repeated_tick_actions) {
    Game a(7);
    Game b(7);
    a.advance_ticks(50);
    for (int i = 0; i < 50; ++i) b.apply(Action::Tick);
    const GameSnapshot sa = a.snapshot();
    const GameSnapshot sb = b.snapshot();
    CHECK_EQ(sa.tick, sb.tick);
    CHECK_EQ(sa.board.hash(), sb.board.hash());
}

TEST(game, action_token_roundtrip) {
    CHECK(action_from_token("L").value() == Action::Left);
    CHECK(action_from_token("R").value() == Action::Right);
    CHECK(action_from_token("CW").value() == Action::RotateCW);
    CHECK(action_from_token("CCW").value() == Action::RotateCCW);
    CHECK(action_from_token("180").value() == Action::Rotate180);
    CHECK(action_from_token("D").value() == Action::SoftDrop);
    CHECK(action_from_token("HD").value() == Action::HardDrop);
    CHECK(action_from_token("HOLD").value() == Action::Hold);
    CHECK(action_from_token("T").value() == Action::Tick);
    CHECK_FALSE(action_from_token("ZZZ").has_value());
    CHECK_EQ(std::string(action_token(Action::Rotate180)), std::string("180"));
}

TEST(game, action_repeat_from_token_parses_suffix) {
    CHECK_EQ(action_repeat_from_token("L"), 1);
    CHECK_EQ(action_repeat_from_token("L2"), 2);
    CHECK_EQ(action_repeat_from_token("D3"), 3);
    CHECK_EQ(action_repeat_from_token("T120"), 120);
    CHECK_EQ(action_repeat_from_token("180"), 1);
}

TEST(game, run_script_tick_limit_stops_simulation) {
    const GameSnapshot s = run_script(1, "T1000", 100);
    CHECK_EQ(s.tick, static_cast<std::uint64_t>(100));
}

// Разбор сценария вынесен в отдельную функцию, потому что от него зависит проверка
// пользовательского ввода в CLI: неизвестный токен должен быть виден вызывающему,
// а не тихо пропускаться внутри прогона.
TEST(game, split_script_separates_tokens) {
    CHECK_EQ(split_script("HD").size(), static_cast<std::size_t>(1));
    CHECK_EQ(split_script("L3 CW HD").size(), static_cast<std::size_t>(3));
    CHECK_EQ(split_script("HD,HD,HD").size(), static_cast<std::size_t>(3));
    CHECK_EQ(split_script("  L \t CW \n HD  ").size(), static_cast<std::size_t>(3));

    const std::vector<std::string> tokens = split_script("T30, L2");
    CHECK_EQ(tokens.at(0), std::string("T30"));
    CHECK_EQ(tokens.at(1), std::string("L2"));

    CHECK_EQ(split_script("").size(), static_cast<std::size_t>(0));
    CHECK_EQ(split_script("   ,, ").size(), static_cast<std::size_t>(0));
}

TEST(game, split_script_keeps_unknown_token_for_validation) {
    const std::vector<std::string> tokens = split_script("XX HD");
    CHECK_EQ(tokens.size(), static_cast<std::size_t>(2));
    CHECK_EQ(tokens.at(0), std::string("XX"));
    CHECK_FALSE(action_from_token(tokens.at(0)).has_value());
    CHECK(action_from_token(tokens.at(1)).has_value());
}

// Тесты очков (docs/spec.md, раздел 8, п.4 и раздел 4).
#include "tetris/core/scoring.hpp"

#include "test_framework.hpp"

#include <string>

using namespace tetris;

namespace {

bool has_event(const ScoreDelta& d, const std::string& name) {
    for (const std::string& e : d.events) {
        if (e == name) return true;
    }
    return false;
}

}  // namespace

TEST(scoring, level_for_lines) {
    CHECK_EQ(level_for_lines(0), 1);
    CHECK_EQ(level_for_lines(9), 1);
    CHECK_EQ(level_for_lines(10), 2);
    CHECK_EQ(level_for_lines(19), 2);
    CHECK_EQ(level_for_lines(20), 3);
    CHECK_EQ(level_for_lines(100), 11);
}

TEST(scoring, gravity_table_matches_specification) {
    const int expected[31] = {48, 48, 43, 38, 33, 28, 23, 18, 13, 8, 6, 5, 5, 4, 4, 4,
                              3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1};
    for (int level = 0; level <= 30; ++level) {
        CHECK_EQ(gravity_frames_per_row(level), expected[level]);
    }
    CHECK_EQ(gravity_frames_per_row(29), 1);
    CHECK_EQ(gravity_frames_per_row(100), 1);
}

TEST(scoring, drop_points) {
    CHECK_EQ(soft_drop_points(0), 0);
    CHECK_EQ(soft_drop_points(1), 1);
    CHECK_EQ(soft_drop_points(7), 7);
    CHECK_EQ(hard_drop_points(0), 0);
    CHECK_EQ(hard_drop_points(1), 2);
    CHECK_EQ(hard_drop_points(9), 18);
}

TEST(scoring, line_clear_base_points) {
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{1, false, false, false, false});
        CHECK_EQ(d.points, 100);
        CHECK_EQ(st.score, 100);
        CHECK_EQ(st.lines, 1);
        CHECK(has_event(d, "clear:single"));
    }
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{2, false, false, false, false});
        CHECK_EQ(d.points, 300);
        CHECK(has_event(d, "clear:double"));
    }
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{3, false, false, false, false});
        CHECK_EQ(d.points, 500);
        CHECK(has_event(d, "clear:triple"));
    }
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{4, false, false, false, false});
        CHECK_EQ(d.points, 800);
        CHECK(has_event(d, "clear:tetris"));
    }
}

TEST(scoring, points_multiplied_by_level) {
    ScoreState st;
    st.level = 3;
    const ScoreDelta d = score_lock(st, ClearResult{1, false, false, false, false});
    CHECK_EQ(d.points, 300);
}

TEST(scoring, level_grows_but_multiplier_is_pre_clear_level) {
    ScoreState st;
    st.lines = 9;
    st.level = 1;
    const ScoreDelta d = score_lock(st, ClearResult{1, false, false, false, false});
    CHECK_EQ(d.points, 100);  // очки за уровень до повышения
    CHECK_EQ(st.lines, 10);
    CHECK_EQ(st.level, 2);
}

TEST(scoring, tspin_points) {
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{1, true, false, false, false});
        CHECK_EQ(d.points, 800);
        CHECK(has_event(d, "clear:tspin_single"));
    }
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{2, true, false, false, false});
        CHECK_EQ(d.points, 1200);
    }
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{3, true, false, false, false});
        CHECK_EQ(d.points, 1600);
    }
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{0, false, true, false, false});
        CHECK_EQ(d.points, 100);  // T-spin mini без строк
        CHECK(has_event(d, "clear:tspin_mini"));
    }
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{1, false, true, false, false});
        CHECK_EQ(d.points, 200);
    }
}

TEST(scoring, perfect_clear_bonus) {
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{1, false, false, true, false});
        CHECK_EQ(d.points, 100 + 800);
        CHECK(has_event(d, "perfect_clear"));
    }
    {
        ScoreState st;
        const ScoreDelta d = score_lock(st, ClearResult{4, false, false, true, false});
        CHECK_EQ(d.points, 800 + 2000);
    }
}

TEST(scoring, combo_series) {
    ScoreState st;
    const ScoreDelta first = score_lock(st, ClearResult{1, false, false, false, false});
    CHECK_EQ(first.points, 100);
    CHECK_EQ(st.combo, 0);
    const ScoreDelta second = score_lock(st, ClearResult{1, false, false, false, false});
    CHECK_EQ(second.points, 100 + 50);  // 50 × combo(1) × level(1)
    CHECK_EQ(st.combo, 1);
    CHECK(has_event(second, "combo"));
}

TEST(scoring, lock_without_clear_resets_combo) {
    ScoreState st;
    score_lock(st, ClearResult{1, false, false, false, false});
    CHECK_EQ(st.combo, 0);
    score_lock(st, ClearResult{0, false, false, false, false});
    CHECK_EQ(st.combo, -1);
    const ScoreDelta again = score_lock(st, ClearResult{1, false, false, false, false});
    CHECK_EQ(again.points, 100);  // новая серия начинается снова с нуля
}

TEST(scoring, back_to_back_multiplies_difficult_clears) {
    ScoreState st;
    const ScoreDelta first = score_lock(st, ClearResult{4, false, false, false, false});
    CHECK_EQ(first.points, 800);
    CHECK(st.back_to_back);
    const ScoreDelta second = score_lock(st, ClearResult{4, false, false, false, false});
    // ×1.5 к очкам очистки (1200) плюс combo 50 × 1 × 1.
    CHECK_EQ(second.points, 1200 + 50);
    CHECK(has_event(second, "b2b"));
}

TEST(scoring, normal_clear_breaks_back_to_back) {
    ScoreState st;
    score_lock(st, ClearResult{4, false, false, false, false});
    const ScoreDelta single = score_lock(st, ClearResult{1, false, false, false, false});
    CHECK_EQ(single.points, 100 + 50);  // combo, но без b2b
    CHECK_FALSE(has_event(single, "b2b"));
    CHECK_FALSE(st.back_to_back);
}

TEST(scoring, tspin_also_counts_as_back_to_back) {
    ScoreState st;
    score_lock(st, ClearResult{0, true, false, false, false});  // полный T-spin без строк
    CHECK(st.back_to_back);
    const ScoreDelta d = score_lock(st, ClearResult{4, false, false, false, false});
    // Тетрис ×1.5 к очкам очистки; combo = 0, поэтому бонуса серии нет.
    CHECK_EQ(d.points, 1200);
    CHECK(has_event(d, "b2b"));
}

TEST(scoring, clear_label_names) {
    CHECK_EQ(clear_label(ClearResult{1, false, false, false, false}), std::string("single"));
    CHECK_EQ(clear_label(ClearResult{2, false, false, false, false}), std::string("double"));
    CHECK_EQ(clear_label(ClearResult{3, false, false, false, false}), std::string("triple"));
    CHECK_EQ(clear_label(ClearResult{4, false, false, false, false}), std::string("tetris"));
    CHECK_EQ(clear_label(ClearResult{1, true, false, false, false}), std::string("tspin_single"));
    CHECK_EQ(clear_label(ClearResult{2, true, false, false, false}), std::string("tspin_double"));
    CHECK_EQ(clear_label(ClearResult{3, true, false, false, false}), std::string("tspin_triple"));
    CHECK_EQ(clear_label(ClearResult{0, false, true, false, false}), std::string("tspin_mini"));
}

// Начисление очков по guideline-таблице (docs/spec.md, раздел 4).
#include "tetris/core/scoring.hpp"

#include <array>

namespace tetris {

namespace {
// Таблицы очков очистки (без уровня).
constexpr std::array<long long, 5> kLinePoints{0, 100, 300, 500, 800};         // 4.1
constexpr std::array<long long, 4> kTspinPoints{400, 800, 1200, 1600};         // 4.2 (полный)
constexpr std::array<long long, 4> kTspinMiniPoints{100, 200, 400, 600};       // 4.2 (mini)
constexpr std::array<long long, 5> kPerfectClearBonus{0, 800, 1200, 1800, 2000};  // 4.3
}  // namespace

long long soft_drop_points(int cells) {
    return cells > 0 ? static_cast<long long>(cells) : 0;
}

long long hard_drop_points(int cells) {
    return cells > 0 ? 2LL * static_cast<long long>(cells) : 0;
}

int level_for_lines(int lines) {
    if (lines < 0) {
        lines = 0;
    }
    return lines / 10 + 1;
}

int gravity_frames_per_row(int level) {
    if (level <= 1) return 48;
    switch (level) {
        case 2: return 43;
        case 3: return 38;
        case 4: return 33;
        case 5: return 28;
        case 6: return 23;
        case 7: return 18;
        case 8: return 13;
        case 9: return 8;
        case 10: return 6;
        default: break;
    }
    if (level <= 12) return 5;
    if (level <= 15) return 4;
    if (level <= 19) return 3;
    if (level <= 28) return 2;
    return 1;
}

std::string clear_label(const ClearResult& result) {
    if (result.tspin) {
        switch (result.rows) {
            case 1: return "tspin_single";
            case 2: return "tspin_double";
            case 3: return "tspin_triple";
            default: return "tspin";
        }
    }
    if (result.tspin_mini) {
        return "tspin_mini";
    }
    switch (result.rows) {
        case 1: return "single";
        case 2: return "double";
        case 3: return "triple";
        case 4: return "tetris";
        default: return "";
    }
}

ScoreDelta score_lock(ScoreState& state, const ClearResult& result) {
    ScoreDelta delta;

    int rows = result.rows;
    if (rows < 0) rows = 0;
    if (rows > 4) rows = 4;

    const bool line_clear = rows > 0;
    const bool clear_event = line_clear || result.tspin || result.tspin_mini;

    // Очки очистки (4.1/4.2), умноженные на текущий уровень.
    long long base = 0;
    if (result.tspin) {
        base = kTspinPoints[static_cast<std::size_t>(rows)];
    } else if (result.tspin_mini) {
        base = kTspinMiniPoints[static_cast<std::size_t>(rows)];
    } else if (line_clear) {
        base = kLinePoints[static_cast<std::size_t>(rows)];
    }
    base *= state.level;

    // Back-to-back (4.6): сложная очистка сразу после сложной — ×1.5 к очкам очистки.
    const bool difficult = (rows == 4) || result.tspin || result.tspin_mini;
    bool b2b_applied = false;
    if (clear_event && difficult && state.back_to_back) {
        base = base * 3 / 2;
        b2b_applied = true;
    }
    if (clear_event) {
        state.back_to_back = difficult;
    }

    // Perfect clear (4.3) добавляется к очкам очистки.
    long long perfect_bonus = 0;
    if (line_clear && result.perfect_clear) {
        perfect_bonus = kPerfectClearBonus[static_cast<std::size_t>(rows)];
    }

    // Combo (4.5): серия очисток подряд.
    long long combo_bonus = 0;
    if (line_clear) {
        state.combo += 1;
        if (state.combo > 0) {
            combo_bonus = 50LL * state.combo * state.level;
        }
    } else {
        state.combo = -1;
    }

    delta.points = base + perfect_bonus + combo_bonus;
    state.score += delta.points;

    // Строки и уровень обновляются после начисления очков.
    state.lines += rows;
    state.level = level_for_lines(state.lines);

    if (clear_event) {
        delta.events.push_back("clear:" + clear_label(result));
    }
    if (b2b_applied) {
        delta.events.push_back("b2b");
    }
    if (line_clear && result.perfect_clear) {
        delta.events.push_back("perfect_clear");
    }
    if (state.combo > 0) {
        delta.events.push_back("combo");
    }
    return delta;
}

}  // namespace tetris

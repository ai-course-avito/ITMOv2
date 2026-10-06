// Подсчёт очков по guideline-таблице (см. docs/spec.md, раздел 4).
#pragma once

#include <string>
#include <vector>

#include "tetris/core/types.hpp"

namespace tetris {

// Результат укладки фигуры — вход для подсчёта очков.
struct ClearResult {
    int rows{0};               // сколько строк удалено: 0..4
    bool tspin{false};         // T-spin (полный, не mini)
    bool tspin_mini{false};    // T-spin mini
    bool perfect_clear{false}; // поле пустое после очистки
    bool used_hold{false};     // фигура взята из hold
};

struct ScoreState {
    long long score{0};
    int lines{0};
    int level{1};
    int combo{-1};          // -1 — серии нет; 0 — первая очистка серии
    bool back_to_back{false};
    int soft_drop_cells{0}; // суммарно клеток, пройденных софт-дропом
    int hard_drop_cells{0}; // суммарно клеток, пройденных хард-дропом
};

struct ScoreDelta {
    long long points{0};
    std::vector<std::string> events;  // человекочитаемые метки для отчёта и MCP
};

// Начисляет очки за укладку и обновляет состояние (в т.ч. combo / back-to-back / level).
ScoreDelta score_lock(ScoreState& state, const ClearResult& result);

// Начисляет очки за софт-/хард-дроп одной клетки.
long long soft_drop_points(int cells);
long long hard_drop_points(int cells);

// Уровень по числу удалённых строк: каждые 10 строк — новый уровень.
int level_for_lines(int lines);

// Кадров на одну клетку падения при 60 тиках в секунду (guideline-таблица).
int gravity_frames_per_row(int level);

// Человекочитаемое имя очистки: "single", "double", "triple", "tetris",
// "tspin_mini", "tspin_single", "tspin_double", "tspin_triple".
std::string clear_label(const ClearResult& result);

}  // namespace tetris

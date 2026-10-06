// Ядро игры: состояние, обработка ввода, гравитация, hold, детект T-spin'ов.
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "tetris/core/bag.hpp"
#include "tetris/core/board.hpp"
#include "tetris/core/pieces.hpp"
#include "tetris/core/scoring.hpp"
#include "tetris/core/types.hpp"

namespace tetris {

// Все входные воздействия игры. Tick продвигает гравитацию на один кадр.
enum class Action {
    Left = 0,
    Right,
    RotateCW,
    RotateCCW,
    Rotate180,
    SoftDrop,
    HardDrop,
    Hold,
    Tick,
};

const char* action_token(Action a);
// Разбор токена сценария: "L","R","CW","CCW","180","D","HD","HOLD","T".
// "T12" — двенадцать тиков (число после T), "D3" — три софт-дропа.
std::optional<Action> action_from_token(const std::string& token);
// Сколько раз применить действие (суффикс-число у токена; по умолчанию 1).
int action_repeat_from_token(const std::string& token);
// Разбирает сценарий на токены: разделители — пробел, запятая, табуляция,
// перевод строки. Нужен CLI для проверки ввода до запуска партии (см. выше).
std::vector<std::string> split_script(const std::string& script);

struct ActivePiece {
    PieceType type{PieceType::I};
    Rotation rotation{Rotation::Spawn};
    Point pos{0, 0};  // положение бокса 4x4 на поле
    Shape shape{};    // кэш piece_shape(type, rotation)
};

struct GameSnapshot {
    std::uint64_t seed{0};
    std::uint64_t tick{0};          // число обработанных тиков гравитации
    int lines{0};
    int level{1};
    long long score{0};
    int combo{-1};
    bool back_to_back{false};
    bool game_over{false};
    bool hold_used{false};                 // hold уже использован для текущей фигуры
    std::optional<PieceType> hold{};
    std::vector<PieceType> next{};         // очередь next (5 фигур)
    std::optional<ActivePiece> active{};
    std::optional<Point> ghost{};          // позиция призрака для активной фигуры
    Board board{};                         // поле без активной фигуры
    int holes{0};                          // count_holes() по полю
    std::vector<std::string> events{};     // события последнего действия
};

class Game {
public:
    explicit Game(std::uint64_t seed = 0);

    void reset(std::uint64_t seed);

    // Применяет действие. Возвращает true, если состояние изменилось.
    bool apply(Action action);

    // Продвигает гравитацию на n кадров (эквивалент n действий Tick).
    void advance_ticks(int n);

    // Снапшот состояния. Активная фигура в поле не отражена — только в active.
    GameSnapshot snapshot() const;

    bool game_over() const { return game_over_; }

private:
    // Внутренние операции.
    bool try_move(int dx, int dy, std::string event);
    bool try_rotate(Rotation target, std::string event);
    void spawn_next_piece();
    void lock_active_piece();
    bool active_locked_out() const;
    void apply_gravity_tick();
    void reset_lock_delay();
    void update_ghost();
    bool check_tspin(std::size_t* filled_corners) const;
    void push_event(std::string event);
    void fill_snapshot(GameSnapshot& out) const;

    std::uint64_t seed_{0};
    Board board_{};
    PieceBag bag_{0};
    ScoreState score_{};
    std::optional<ActivePiece> active_{};
    std::optional<PieceType> hold_{};
    bool hold_used_{false};
    std::optional<Point> ghost_{};
    std::uint64_t tick_{0};
    bool game_over_{false};
    int gravity_accumulator_{0};
    int lock_delay_ticks_{0};
    int lock_resets_{0};
    std::optional<PieceType> last_lock_type_{};
    bool last_lock_was_rotation_{false};
    std::vector<std::string> events_{};
};

// Кадров на клетку падения для уровня (см. scoring.hpp).
constexpr int kLockDelayTicks = 30;       // 500 мс при 60 тиках/с
constexpr int kMaxLockResets = 15;
constexpr int kNextQueueSize = 5;

// Прогоняет сценарий (токены через пробел или запятую) и возвращает снапшот.
// Используется тестами, CLI и через него — MCP-инструментом tetris_sim.
GameSnapshot run_script(std::uint64_t seed, const std::string& script, int max_ticks);

}  // namespace tetris

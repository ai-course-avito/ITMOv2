// Реализация ядра игры: спавн, гравитация, SRS-поворот, hold, lock delay,
// детект T-spin, сценарии (см. game.hpp и docs/spec.md, разделы 2 и 5).
#include "tetris/core/game.hpp"

#include <cctype>
#include <cstddef>
#include <string>
#include <utility>

namespace tetris {

namespace {

// Разобранный токен сценария: действие и число повторов (суффикс-число).
struct ParsedToken {
    std::optional<Action> action;
    int repeat{1};
};

bool digits_only(const std::string& s) {
    for (char c : s) {
        if (c < '0' || c > '9') return false;
    }
    return true;
}

ParsedToken parse_token(const std::string& raw) {
    std::string upper;
    upper.reserve(raw.size());
    for (char c : raw) {
        upper.push_back(static_cast<char>(std::toupper(static_cast<unsigned char>(c))));
    }

    struct Entry {
        const char* name;
        Action action;
    };
    // Порядок: сначала длинные имена, чтобы "HOLD" не разобралось как "HD"+сдвиг.
    static const Entry kNames[] = {
        {"HOLD", Action::Hold},
        {"CCW", Action::RotateCCW},
        {"180", Action::Rotate180},
        {"CW", Action::RotateCW},
        {"HD", Action::HardDrop},
        {"L", Action::Left},
        {"R", Action::Right},
        {"D", Action::SoftDrop},
        {"T", Action::Tick},
    };

    for (const Entry& e : kNames) {
        const std::string name(e.name);
        if (upper.size() >= name.size() && upper.compare(0, name.size(), name) == 0) {
            const std::string suffix = upper.substr(name.size());
            if (!digits_only(suffix)) {
                continue;
            }
            int repeat = 1;
            if (!suffix.empty()) {
                long value = 0;
                for (char c : suffix) {
                    value = value * 10 + (c - '0');
                    if (value > 1000000) {
                        value = 1000000;
                        break;
                    }
                }
                repeat = value < 1 ? 1 : static_cast<int>(value);
            }
            return ParsedToken{e.action, repeat};
        }
    }
    return ParsedToken{std::nullopt, 1};
}

// Полностью пустое ли поле (perfect clear считается по видимым и буферным строкам).
bool board_is_empty(const Board& board) {
    for (int y = 0; y < Board::kHeight; ++y) {
        for (int x = 0; x < Board::kWidth; ++x) {
            if (board.cell(x, y) != Board::kEmpty) {
                return false;
            }
        }
    }
    return true;
}

// Поставить фигуру указанного типа в спавн-позицию.
void place_at_spawn(std::optional<ActivePiece>& active, const Board& board, PieceType type,
                    bool& hold_used, int& gravity_acc, int& lock_ticks, int& lock_resets,
                    bool& game_over) {
    ActivePiece piece;
    piece.type = type;
    piece.rotation = Rotation::Spawn;
    piece.pos = Board::spawn_origin();
    piece.shape = piece_shape(type, Rotation::Spawn);
    active = piece;
    hold_used = false;
    gravity_acc = 0;
    lock_ticks = 0;
    lock_resets = 0;
    if (!board.is_free(piece.shape, piece.pos)) {
        game_over = true;  // блок-аут: спавн-позиция занята
    }
}

// Заняты ли оба угла со стороны «носа» фигуры T (для полного T-spin'а).
bool nose_corners_filled(const Board& board, Point pos, Rotation rotation) {
    Point a{0, 0};
    Point b{0, 0};
    switch (rotation) {
        case Rotation::Spawn: a = Point{0, 2}; b = Point{2, 2}; break;  // нос вверх
        case Rotation::Right: a = Point{2, 0}; b = Point{2, 2}; break;  // нос вправо
        case Rotation::Two:   a = Point{0, 0}; b = Point{2, 0}; break;  // нос вниз
        case Rotation::Left:  a = Point{0, 0}; b = Point{0, 2}; break;  // нос влево
    }
    const auto filled = [&](Point offset) {
        const int x = pos.x + offset.x;
        const int y = pos.y + offset.y;
        if (x < 0 || x >= Board::kWidth || y < 0 || y >= Board::kHeight) return true;
        return board.cell(x, y) != Board::kEmpty;
    };
    return filled(a) && filled(b);
}

}  // namespace

const char* action_token(Action a) {
    switch (a) {
        case Action::Left: return "L";
        case Action::Right: return "R";
        case Action::RotateCW: return "CW";
        case Action::RotateCCW: return "CCW";
        case Action::Rotate180: return "180";
        case Action::SoftDrop: return "D";
        case Action::HardDrop: return "HD";
        case Action::Hold: return "HOLD";
        case Action::Tick: return "T";
    }
    return "?";
}

std::optional<Action> action_from_token(const std::string& token) {
    return parse_token(token).action;
}

int action_repeat_from_token(const std::string& token) {
    return parse_token(token).repeat;
}

std::vector<std::string> split_script(const std::string& script) {
    std::vector<std::string> tokens;
    std::string current;
    for (char c : script) {
        if (c == ' ' || c == ',' || c == '\t' || c == '\n' || c == '\r') {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
        } else {
            current.push_back(c);
        }
    }
    if (!current.empty()) {
        tokens.push_back(current);
    }
    return tokens;
}

Game::Game(std::uint64_t seed) {
    reset(seed);
}

void Game::reset(std::uint64_t seed) {
    seed_ = seed;
    board_.clear();
    bag_.reseed(seed);
    score_ = ScoreState{};
    active_ = std::nullopt;
    hold_ = std::nullopt;
    hold_used_ = false;
    ghost_ = std::nullopt;
    tick_ = 0;
    game_over_ = false;
    gravity_accumulator_ = 0;
    lock_delay_ticks_ = 0;
    lock_resets_ = 0;
    last_lock_type_ = std::nullopt;
    last_lock_was_rotation_ = false;
    events_.clear();
    spawn_next_piece();
}

bool Game::apply(Action action) {
    if (game_over_) {
        return false;
    }
    // События не-тиковых действий начинают новый набор; тик только дополняет его.
    if (action != Action::Tick) {
        events_.clear();
    }

    switch (action) {
        case Action::Left:
            return try_move(-1, 0, "left");
        case Action::Right:
            return try_move(+1, 0, "right");
        case Action::RotateCW: {
            if (!active_) return false;
            return try_rotate(rotate_cw(active_->rotation), "rotate_cw");
        }
        case Action::RotateCCW: {
            if (!active_) return false;
            return try_rotate(rotate_ccw(active_->rotation), "rotate_ccw");
        }
        case Action::Rotate180: {
            if (!active_) return false;
            // 180 — это два поворота по часовой стрелке, каждый со своей таблицей вылетов.
            const bool first = try_rotate(rotate_cw(active_->rotation), "rotate_180");
            bool second = false;
            if (first) {
                second = try_rotate(rotate_cw(active_->rotation), "rotate_180");
            }
            return first || second;
        }
        case Action::SoftDrop: {
            if (!active_) return false;
            const Point next{active_->pos.x, active_->pos.y - 1};
            if (!board_.is_free(active_->shape, next)) {
                return false;
            }
            active_->pos = next;
            score_.score += soft_drop_points(1);
            score_.soft_drop_cells += 1;
            reset_lock_delay();
            update_ghost();
            push_event("soft_drop");
            return true;
        }
        case Action::HardDrop: {
            if (!active_) return false;
            int distance = 0;
            while (board_.is_free(active_->shape, Point{active_->pos.x, active_->pos.y - 1})) {
                active_->pos.y -= 1;
                ++distance;
            }
            if (distance > 0) {
                score_.score += hard_drop_points(distance);
                score_.hard_drop_cells += distance;
            }
            push_event("hard_drop");
            lock_active_piece();
            return true;
        }
        case Action::Hold: {
            if (!active_ || hold_used_) {
                return false;
            }
            const PieceType current = active_->type;
            PieceType incoming;
            if (hold_) {
                incoming = *hold_;
                hold_ = current;
            } else {
                hold_ = current;
                incoming = bag_.next();
            }
            place_at_spawn(active_, board_, incoming, hold_used_, gravity_accumulator_,
                           lock_delay_ticks_, lock_resets_, game_over_);
            hold_used_ = true;
            last_lock_was_rotation_ = false;
            update_ghost();
            push_event("hold");
            return true;
        }
        case Action::Tick:
            apply_gravity_tick();
            return true;
    }
    return false;
}

void Game::advance_ticks(int n) {
    for (int i = 0; i < n; ++i) {
        apply(Action::Tick);
    }
}

GameSnapshot Game::snapshot() const {
    GameSnapshot out;
    fill_snapshot(out);
    return out;
}

void Game::fill_snapshot(GameSnapshot& out) const {
    out.seed = seed_;
    out.tick = tick_;
    out.lines = score_.lines;
    out.level = score_.level;
    out.score = score_.score;
    out.combo = score_.combo;
    out.back_to_back = score_.back_to_back;
    out.game_over = game_over_;
    out.hold_used = hold_used_;
    out.hold = hold_;
    // peek() не помечен const, поэтому заглядываем вперёд на копии мешка.
    PieceBag lookahead = bag_;
    out.next = lookahead.peek(kNextQueueSize);
    out.active = active_;
    out.ghost = ghost_;
    out.board = board_;
    out.holes = board_.count_holes();
    out.events = events_;
}

bool Game::try_move(int dx, int dy, std::string event) {
    if (!active_) {
        return false;
    }
    const Point next{active_->pos.x + dx, active_->pos.y + dy};
    if (!board_.is_free(active_->shape, next)) {
        return false;
    }
    active_->pos = next;
    last_lock_was_rotation_ = false;
    reset_lock_delay();
    update_ghost();
    push_event(std::move(event));
    return true;
}

bool Game::try_rotate(Rotation target, std::string event) {
    if (!active_) {
        return false;
    }
    const Rotation from = active_->rotation;
    if (from == target) {
        return false;
    }

    const std::vector<Point>& kicks = srs_kicks(active_->type, from, target);
    // O-фигура: пустая таблица трактуется как единственное смещение (0,0).
    const std::vector<Point> fallback{{0, 0}};
    const std::vector<Point>& offsets = kicks.empty() ? fallback : kicks;
    const Shape target_shape = piece_shape(active_->type, target);

    for (std::size_t i = 0; i < offsets.size(); ++i) {
        const Point candidate{active_->pos.x + offsets[i].x, active_->pos.y + offsets[i].y};
        if (!board_.is_free(target_shape, candidate)) {
            continue;
        }
        active_->shape = target_shape;
        active_->rotation = target;
        active_->pos = candidate;
        last_lock_was_rotation_ = true;
        // В last_lock_type_ хранится индекс применённого вылета (0..4): он нужен
        // для условия «поворот на последнем смещении таблицы» в детекте T-spin.
        last_lock_type_ = static_cast<PieceType>(i < kPieceTypeCount ? i : kPieceTypeCount - 1);
        reset_lock_delay();
        update_ghost();
        push_event(std::move(event));
        return true;
    }
    return false;
}

void Game::spawn_next_piece() {
    const PieceType type = bag_.next();
    place_at_spawn(active_, board_, type, hold_used_, gravity_accumulator_, lock_delay_ticks_,
                   lock_resets_, game_over_);
    last_lock_was_rotation_ = false;
    if (game_over_) {
        push_event("game_over");
    }
    update_ghost();
}

void Game::lock_active_piece() {
    if (!active_) {
        return;
    }
    const PieceType type = active_->type;

    ClearResult result;
    if (last_lock_was_rotation_ && type == PieceType::T) {
        std::size_t corners = 0;
        if (check_tspin(&corners)) {
            const bool full_nose = nose_corners_filled(board_, active_->pos, active_->rotation);
            const bool last_kick = last_lock_type_.has_value() &&
                                   static_cast<int>(*last_lock_type_) == 4;
            if (full_nose || last_kick) {
                result.tspin = true;
            } else {
                result.tspin_mini = true;
            }
        }
    }

    board_.lock(active_->shape, active_->pos, type);
    const bool locked_out = active_locked_out();
    result.rows = board_.clear_full_rows();
    result.perfect_clear = board_is_empty(board_);

    const ScoreDelta delta = score_lock(score_, result);
    for (const std::string& e : delta.events) {
        events_.push_back(e);
    }

    active_ = std::nullopt;
    ghost_ = std::nullopt;
    last_lock_was_rotation_ = false;

    if (locked_out) {
        game_over_ = true;
        push_event("lock_out");
        push_event("game_over");
        return;
    }
    spawn_next_piece();
    update_ghost();
}

bool Game::active_locked_out() const {
    if (!active_) {
        return false;
    }
    for (const Point& c : active_->shape) {
        if (active_->pos.y + c.y < Board::kVisibleHeight) {
            return false;
        }
    }
    return true;
}

void Game::apply_gravity_tick() {
    ++tick_;
    if (game_over_ || !active_) {
        return;
    }
    const bool can_fall = board_.is_free(active_->shape, Point{active_->pos.x, active_->pos.y - 1});
    if (can_fall) {
        lock_delay_ticks_ = 0;
        ++gravity_accumulator_;
        const int frames = gravity_frames_per_row(score_.level);
        if (gravity_accumulator_ >= frames) {
            gravity_accumulator_ = 0;
            active_->pos.y -= 1;
        }
    } else {
        gravity_accumulator_ = 0;
        ++lock_delay_ticks_;
        if (lock_delay_ticks_ >= kLockDelayTicks) {
            lock_active_piece();
        }
    }
    update_ghost();
}

void Game::reset_lock_delay() {
    if (!active_) {
        return;
    }
    const bool grounded =
        !board_.is_free(active_->shape, Point{active_->pos.x, active_->pos.y - 1});
    if (!grounded) {
        lock_delay_ticks_ = 0;
        return;
    }
    if (lock_resets_ < kMaxLockResets) {
        ++lock_resets_;
        lock_delay_ticks_ = 0;
    }
}

void Game::update_ghost() {
    if (!active_) {
        ghost_ = std::nullopt;
        return;
    }
    Point position = active_->pos;
    while (board_.is_free(active_->shape, Point{position.x, position.y - 1})) {
        position.y -= 1;
    }
    ghost_ = position;
}

bool Game::check_tspin(std::size_t* filled_corners) const {
    if (filled_corners) {
        *filled_corners = 0;
    }
    if (!active_ || active_->type != PieceType::T) {
        return false;
    }
    // Четыре угла бокса 3x3 вокруг центра T (бокс 3x3 из нижнего левого угла 4x4).
    // Угол занят, если он за границей поля, занят блоком поля или занят клеткой
    // самой фигуры T (в этой модели T всегда накрывает два таких угла).
    static const Point kCorners[4] = {{0, 0}, {2, 0}, {0, 2}, {2, 2}};
    const auto is_own_cell = [&](Point offset) {
        for (const Point& c : active_->shape) {
            if (c == offset) return true;
        }
        return false;
    };
    std::size_t filled = 0;
    for (const Point& c : kCorners) {
        const int x = active_->pos.x + c.x;
        const int y = active_->pos.y + c.y;
        if (x < 0 || x >= Board::kWidth || y < 0 || y >= Board::kHeight) {
            ++filled;  // стена или дно считаются занятым углом
            continue;
        }
        if (board_.cell(x, y) != Board::kEmpty || is_own_cell(c)) {
            ++filled;
        }
    }
    if (filled_corners) {
        *filled_corners = filled;
    }
    return filled >= 3;
}

void Game::push_event(std::string event) {
    events_.push_back(std::move(event));
}

GameSnapshot run_script(std::uint64_t seed, const std::string& script, int max_ticks) {
    Game game(seed);
    if (max_ticks <= 0) {
        max_ticks = 20000;
    }

    std::vector<std::string> tokens = split_script(script);

    long long ticks = 0;
    for (const std::string& token : tokens) {
        const ParsedToken parsed = parse_token(token);
        if (!parsed.action) {
            continue;
        }
        const Action action = *parsed.action;
        const int repeat = parsed.repeat < 1 ? 1 : parsed.repeat;
        for (int i = 0; i < repeat; ++i) {
            game.apply(action);
            if (action == Action::Tick) {
                ++ticks;
                if (ticks >= max_ticks) {
                    return game.snapshot();
                }
            }
            if (game.game_over()) {
                return game.snapshot();
            }
        }
        // После каждого токена, кроме T, идёт один тик гравитации.
        if (action != Action::Tick) {
            game.apply(Action::Tick);
            ++ticks;
            if (ticks >= max_ticks || game.game_over()) {
                return game.snapshot();
            }
        }
    }
    return game.snapshot();
}

}  // namespace tetris

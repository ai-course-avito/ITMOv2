// SDL2-фронтенд: окно, ввод и отрисовка.
//
// Правило границы слоёв (AGENTS.md, раздел 5): игровой логики здесь нет.
// Цикл только читает Game::snapshot() и вызывает game.apply(Action::...) /
// game.advance_ticks(1) — всё остальное делает ядро.
//
// SDL_ttf в зависимостях нет, поэтому текст рисуется самодельным пиксельным
// шрифтом 3x5 из прямоугольников (SDL_RenderFillRect). Список функций SDL
// сверен с /usr/include/SDL2 (SDL 2.32.4), а не по памяти.
#include <SDL.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <system_error>

#include "tetris/core/board.hpp"
#include "tetris/core/game.hpp"
#include "tetris/core/pieces.hpp"
#include "tetris/core/types.hpp"
#include "tetris/ui/highscore.hpp"
#include "tetris/ui/sdl_app.hpp"

namespace {

using tetris::Board;
using tetris::PieceType;
using tetris::Rotation;
using tetris::Shape;

// --- Рекорд (docs/spec.md, AC-3.3) -----------------------------------------
// Само хранение живёт в tetris::highscore (см. highscore.cpp) — модуль без SDL,
// поэтому он покрыт unit-тестами. Здесь только путь по умолчанию.

long long load_best_score() {
    return tetris::read_highscore(tetris::default_highscore_path());
}

void save_best_score(long long score) {
    tetris::write_highscore(tetris::default_highscore_path(), score);
}

// --- Цвета -----------------------------------------------------------------

struct Rgb {
    std::uint8_t r;
    std::uint8_t g;
    std::uint8_t b;
};

constexpr Rgb kBackground{0x0B, 0x0B, 0x12};
constexpr Rgb kFieldBackground{0x0F, 0x0F, 0x17};
constexpr Rgb kGrid{0x1E, 0x1E, 0x2A};
constexpr Rgb kFrame{0x4A, 0x4A, 0x62};
constexpr Rgb kText{0xD8, 0xD8, 0xE8};
constexpr Rgb kTextDim{0x76, 0x76, 0x8E};
constexpr Rgb kAccent{0x4E, 0xD1, 0x6A};
constexpr Rgb kGhost{0x4C, 0x4C, 0x6E};
constexpr Rgb kBlockEdge{0x14, 0x14, 0x1C};
constexpr Rgb kOverlay{0x00, 0x00, 0x00};
constexpr Rgb kGameOver{0xE0, 0x50, 0x50};
constexpr Rgb kPaused{0xE0, 0xC0, 0x50};

// Цвет фигуры по типу — общепринятая раскладка guideline-тетриса.
Rgb piece_color(PieceType type) {
    switch (type) {
        case PieceType::I:
            return {0x2E, 0xD9, 0xE6};
        case PieceType::J:
            return {0x3B, 0x6F, 0xD6};
        case PieceType::L:
            return {0xE8, 0x8A, 0x1B};
        case PieceType::O:
            return {0xE8, 0xD4, 0x2A};
        case PieceType::S:
            return {0x3C, 0xC0, 0x4E};
        case PieceType::T:
            return {0xA4, 0x4F, 0xD6};
        case PieceType::Z:
            return {0xD6, 0x3C, 0x3C};
    }
    return {0x88, 0x88, 0x88};
}

void set_color(SDL_Renderer* renderer, Rgb color, std::uint8_t alpha = 255) {
    SDL_SetRenderDrawColor(renderer, color.r, color.g, color.b, alpha);
}

void fill_rect(SDL_Renderer* renderer, int x, int y, int w, int h, Rgb color,
               std::uint8_t alpha = 255) {
    set_color(renderer, color, alpha);
    SDL_Rect rect{x, y, w, h};
    SDL_RenderFillRect(renderer, &rect);
}

void draw_frame(SDL_Renderer* renderer, int x, int y, int w, int h, Rgb color) {
    set_color(renderer, color);
    SDL_Rect rect{x, y, w, h};
    SDL_RenderDrawRect(renderer, &rect);
}

// filled-клетка с тёмной рамкой либо контур (призрак).
void draw_block(SDL_Renderer* renderer, int x, int y, int size, Rgb color, bool outline) {
    if (outline) {
        set_color(renderer, color);
        SDL_Rect outer{x + 1, y + 1, size - 2, size - 2};
        SDL_RenderDrawRect(renderer, &outer);
        SDL_Rect inner{x + 2, y + 2, size - 4, size - 4};
        SDL_RenderDrawRect(renderer, &inner);
        return;
    }
    fill_rect(renderer, x, y, size, size, color);
    if (size > 4) {
        draw_frame(renderer, x + 1, y + 1, size - 2, size - 2, kBlockEdge);
    }
}

// --- Пиксельный шрифт 3x5 --------------------------------------------------

struct Glyph {
    std::array<const char*, 5> rows;  // пять строк сверху вниз, по три символа
};

struct FontEntry {
    char character;
    Glyph glyph;
};

// '#' — включённый пиксель, ' ' — фон. Заменяет отсутствующий SDL_ttf.
const FontEntry kFont[] = {
    {' ', {"   ", "   ", "   ", "   ", "   "}},
    {'-', {"   ", "   ", "###", "   ", "   "}},
    {':', {"   ", " # ", "   ", " # ", "   "}},
    {'0', {"###", "#.#", "#.#", "#.#", "###"}},
    {'1', {" # ", "## ", " # ", " # ", "###"}},
    {'2', {"## ", "..#", " # ", "#..", "###"}},
    {'3', {"## ", "..#", " # ", "..#", "## "}},
    {'4', {"#.#", "#.#", "###", "..#", "..#"}},
    {'5', {"###", "#..", "## ", "..#", "## "}},
    {'6', {" ##", "#..", "###", "#.#", "###"}},
    {'7', {"###", "..#", " # ", " # ", " # "}},
    {'8', {"###", "#.#", "###", "#.#", "###"}},
    {'9', {"###", "#.#", "###", "..#", "## "}},
    {'A', {".#.", "#.#", "###", "#.#", "#.#"}},
    {'B', {"##.", "#.#", "##.", "#.#", "##."}},
    {'C', {".##", "#..", "#..", "#..", ".##"}},
    {'D', {"##.", "#.#", "#.#", "#.#", "##."}},
    {'E', {"###", "#..", "##.", "#..", "###"}},
    {'F', {"###", "#..", "##.", "#..", "#.."}},
    {'G', {".##", "#..", "#.#", "#.#", ".##"}},
    {'H', {"#.#", "#.#", "###", "#.#", "#.#"}},
    {'I', {"###", ".#.", ".#.", ".#.", "###"}},
    {'J', {"..#", "..#", "..#", "#.#", ".#."}},
    {'K', {"#.#", "#.#", "##.", "#.#", "#.#"}},
    {'L', {"#..", "#..", "#..", "#..", "###"}},
    {'M', {"#.#", "###", "#.#", "#.#", "#.#"}},
    {'N', {"#.#", "###", "###", "#.#", "#.#"}},
    {'O', {".#.", "#.#", "#.#", "#.#", ".#."}},
    {'P', {"##.", "#.#", "##.", "#..", "#.."}},
    {'Q', {".#.", "#.#", "#.#", "##.", ".##"}},
    {'R', {"##.", "#.#", "##.", "#.#", "#.#"}},
    {'S', {".##", "#..", ".#.", "..#", "##."}},
    {'T', {"###", ".#.", ".#.", ".#.", ".#."}},
    {'U', {"#.#", "#.#", "#.#", "#.#", ".#."}},
    {'V', {"#.#", "#.#", "#.#", ".#.", ".#."}},
    {'W', {"#.#", "#.#", "#.#", "###", "#.#"}},
    {'X', {"#.#", "#.#", ".#.", "#.#", "#.#"}},
    {'Y', {"#.#", "#.#", ".#.", ".#.", ".#."}},
    {'Z', {"###", "..#", ".#.", "#..", "###"}},
};

const Glyph* glyph_for(char character) {
    if (character >= 'a' && character <= 'z') {
        character = static_cast<char>(character - 'a' + 'A');
    }
    for (const FontEntry& entry : kFont) {
        if (entry.character == character) {
            return &entry.glyph;
        }
    }
    return nullptr;
}

// Ширина строки: каждый глиф 3 пикселя плюс 1 пиксель пробела.
int text_width(const std::string& text, int scale) {
    if (text.empty()) {
        return 0;
    }
    return static_cast<int>(text.size()) * 4 * scale - scale;
}

void draw_text(SDL_Renderer* renderer, const std::string& text, int x, int y, int scale,
               Rgb color) {
    set_color(renderer, color);
    int cursor = x;
    for (const char raw : text) {
        const Glyph* glyph = glyph_for(raw);
        if (glyph != nullptr) {
            for (int row = 0; row < 5; ++row) {
                const char* line = glyph->rows[static_cast<std::size_t>(row)];
                for (int column = 0; column < 3; ++column) {
                    if (line[column] != '#') {
                        continue;
                    }
                    SDL_Rect pixel{cursor + column * scale, y + row * scale, scale, scale};
                    SDL_RenderFillRect(renderer, &pixel);
                }
            }
        }
        cursor += 4 * scale;
    }
}

void draw_text_centered(SDL_Renderer* renderer, const std::string& text, int center_x, int y,
                        int scale, Rgb color) {
    draw_text(renderer, text, center_x - text_width(text, scale) / 2, y, scale, color);
}

// --- Раскладка -------------------------------------------------------------

struct Layout {
    int cell{28};
    int field_x{0};
    int field_y{0};
    int field_w{0};
    int field_h{0};
    int panel_x{0};
    int panel_w{0};
    int window_w{0};
    int window_h{0};
};

Layout make_layout(const tetris::SdlConfig& config) {
    Layout layout;
    layout.cell = config.cell_px > 0 ? config.cell_px : 28;
    const int margin = layout.cell;
    const int gap = layout.cell;
    const int panel_cells = 8;

    layout.field_w = Board::kWidth * layout.cell;
    layout.field_h = Board::kVisibleHeight * layout.cell;
    layout.field_x = margin;
    layout.field_y = margin;
    layout.panel_w = panel_cells * layout.cell;
    layout.panel_x = layout.field_x + layout.field_w + gap;
    layout.window_w =
        config.window_width > 0 ? config.window_width : layout.panel_x + layout.panel_w + margin;
    layout.window_h =
        config.window_height > 0 ? config.window_height : layout.field_y + layout.field_h + margin;
    return layout;
}

// --- Отрисовка игровых элементов -------------------------------------------

void draw_shape(SDL_Renderer* renderer, const Shape& shape, tetris::Point origin,
                const Layout& layout, Rgb color, bool outline) {
    for (const tetris::Point& cell : shape) {
        const int board_x = origin.x + cell.x;
        const int board_y = origin.y + cell.y;
        if (board_x < 0 || board_x >= Board::kWidth) {
            continue;
        }
        if (board_y < 0 || board_y >= Board::kVisibleHeight) {
            continue;
        }
        const int px = layout.field_x + board_x * layout.cell;
        // y = 0 — нижняя видимая строка, поэтому строка переворачивается.
        const int py = layout.field_y + (Board::kVisibleHeight - 1 - board_y) * layout.cell;
        draw_block(renderer, px, py, layout.cell, color, outline);
    }
}

// Фигура в окошке предпросмотра: форма центрируется по своим границам,
// потому что спавн-форма занимает не весь бокс 4x4.
void draw_preview(SDL_Renderer* renderer, PieceType type, int box_x, int box_y, int box_w,
                  int box_h, int preview_cell) {
    const Shape shape = tetris::piece_shape(type, Rotation::Spawn);
    int min_x = 4;
    int max_x = -1;
    int min_y = 4;
    int max_y = -1;
    for (const tetris::Point& cell : shape) {
        min_x = std::min(min_x, cell.x);
        max_x = std::max(max_x, cell.x);
        min_y = std::min(min_y, cell.y);
        max_y = std::max(max_y, cell.y);
    }
    if (max_x < min_x || max_y < min_y) {
        return;
    }
    const int shape_w = (max_x - min_x + 1) * preview_cell;
    const int shape_h = (max_y - min_y + 1) * preview_cell;
    const int offset_x = box_x + (box_w - shape_w) / 2;
    const int offset_y = box_y + (box_h - shape_h) / 2;
    const Rgb color = piece_color(type);
    for (const tetris::Point& cell : shape) {
        const int px = offset_x + (cell.x - min_x) * preview_cell;
        const int py = offset_y + (max_y - cell.y) * preview_cell;  // y вверх
        draw_block(renderer, px, py, preview_cell, color, false);
    }
}

void draw_well(SDL_Renderer* renderer, const tetris::GameSnapshot& snapshot, const Layout& layout,
               const tetris::SdlConfig& config) {
    fill_rect(renderer, layout.field_x, layout.field_y, layout.field_w, layout.field_h,
              kFieldBackground);

    set_color(renderer, kGrid);
    for (int x = 1; x < Board::kWidth; ++x) {
        const int px = layout.field_x + x * layout.cell;
        SDL_RenderDrawLine(renderer, px, layout.field_y, px, layout.field_y + layout.field_h - 1);
    }
    for (int y = 1; y < Board::kVisibleHeight; ++y) {
        const int py = layout.field_y + y * layout.cell;
        SDL_RenderDrawLine(renderer, layout.field_x, py, layout.field_x + layout.field_w - 1, py);
    }

    // Призрак рисуется до фигуры, чтобы активная фигура осталась сверху.
    if (config.show_ghost && snapshot.ghost.has_value() && snapshot.active.has_value()) {
        draw_shape(renderer, snapshot.active->shape, *snapshot.ghost, layout, kGhost, true);
    }

    // Уложенные клетки поля.
    for (int y = 0; y < Board::kVisibleHeight; ++y) {
        for (int x = 0; x < Board::kWidth; ++x) {
            const std::uint8_t value = snapshot.board.cell(x, y);
            if (value == Board::kEmpty) {
                continue;
            }
            const int index = static_cast<int>(value) - 1;
            if (index < 0 || index >= tetris::kPieceTypeCount) {
                continue;
            }
            const int px = layout.field_x + x * layout.cell;
            const int py = layout.field_y + (Board::kVisibleHeight - 1 - y) * layout.cell;
            draw_block(renderer, px, py, layout.cell,
                       piece_color(static_cast<PieceType>(index)), false);
        }
    }

    if (snapshot.active.has_value()) {
        draw_shape(renderer, snapshot.active->shape, snapshot.active->pos, layout,
                   piece_color(snapshot.active->type), false);
    }

    draw_frame(renderer, layout.field_x - 2, layout.field_y - 2, layout.field_w + 4,
               layout.field_h + 4, kFrame);
}

void draw_panel(SDL_Renderer* renderer, const tetris::GameSnapshot& snapshot,
                const Layout& layout, long long best) {
    const int label_scale = std::max(2, layout.cell / 9);
    const int line_h = 5 * label_scale + 5;
    const int preview_cell = std::max(6, layout.cell / 2);
    const int preview_w = 4 * preview_cell;
    const int preview_h = 3 * preview_cell;

    int y = layout.field_y;

    // Hold.
    draw_text(renderer, "HOLD", layout.panel_x, y, label_scale, kText);
    y += line_h;
    draw_frame(renderer, layout.panel_x, y, preview_w, preview_h,
               snapshot.hold_used ? kTextDim : kFrame);
    if (snapshot.hold.has_value()) {
        draw_preview(renderer, *snapshot.hold, layout.panel_x, y, preview_w, preview_h,
                     preview_cell);
    }
    y += preview_h + line_h;

    // Очередь next: по спецификации всегда пять фигур.
    draw_text(renderer, "NEXT", layout.panel_x, y, label_scale, kText);
    y += line_h;
    const std::size_t next_count = std::min<std::size_t>(snapshot.next.size(), 5U);
    for (std::size_t i = 0; i < next_count; ++i) {
        draw_frame(renderer, layout.panel_x, y, preview_w, preview_h, kFrame);
        draw_preview(renderer, snapshot.next[i], layout.panel_x, y, preview_w, preview_h,
                     preview_cell);
        y += preview_h + 6;
    }
    y += line_h;

    // HUD.
    draw_text(renderer, "SCORE " + std::to_string(snapshot.score), layout.panel_x, y, label_scale,
              kText);
    y += line_h;
    draw_text(renderer, "LINES " + std::to_string(snapshot.lines), layout.panel_x, y, label_scale,
              kText);
    y += line_h;
    draw_text(renderer, "LEVEL " + std::to_string(snapshot.level), layout.panel_x, y, label_scale,
              kText);
    y += line_h;
    draw_text(renderer, "COMBO " + std::to_string(snapshot.combo), layout.panel_x, y, label_scale,
              kText);
    y += line_h;
    draw_text(renderer, snapshot.back_to_back ? "B2B ON" : "B2B OFF", layout.panel_x, y,
              label_scale, snapshot.back_to_back ? kAccent : kTextDim);
    y += line_h;
    // Рекорд с диска (AC-3.3): показываем и в HUD, и на экране Game Over.
    draw_text(renderer, "BEST " + std::to_string(best), layout.panel_x, y, label_scale, kTextDim);
    y += line_h;

    // Управление внизу панели — короткая шпаргалка для игрока.
    const int hint_scale = std::max(1, layout.cell / 14);
    y += line_h;
    draw_text(renderer, "ESC EXIT", layout.panel_x, y, hint_scale, kTextDim);
    y += 5 * hint_scale + 4;
    draw_text(renderer, "P PAUSE", layout.panel_x, y, hint_scale, kTextDim);
}

void draw_message_overlay(SDL_Renderer* renderer, const Layout& layout, const std::string& title,
                          Rgb title_color, const std::string& hint) {
    fill_rect(renderer, layout.field_x, layout.field_y, layout.field_w, layout.field_h, kOverlay,
              200);
    const int title_scale = std::max(3, layout.cell / 6);
    const int hint_scale = std::max(2, layout.cell / 10);
    const int center_x = layout.field_x + layout.field_w / 2;
    const int title_y = layout.field_y + layout.field_h / 2 - 4 * title_scale;
    draw_text_centered(renderer, title, center_x, title_y, title_scale, title_color);
    const int hint_y = title_y + 5 * title_scale + 4 * hint_scale;
    draw_text_centered(renderer, hint, center_x, hint_y, hint_scale, kText);
}

void render_frame(SDL_Renderer* renderer, const tetris::GameSnapshot& snapshot,
                  const Layout& layout, const tetris::SdlConfig& config, bool paused,
                  long long best) {
    set_color(renderer, kBackground);
    SDL_RenderClear(renderer);

    draw_well(renderer, snapshot, layout, config);
    draw_panel(renderer, snapshot, layout, best);

    if (snapshot.game_over) {
        draw_message_overlay(renderer, layout, "GAME OVER", kGameOver,
                             "PRESS R   BEST " + std::to_string(best));
    } else if (paused) {
        draw_message_overlay(renderer, layout, "PAUSED", kPaused, "PRESS P");
    }

    SDL_RenderPresent(renderer);
}

// --- Разбор событий --------------------------------------------------------

// true — нужно завершить цикл.
bool handle_event(const SDL_Event& event, tetris::Game& game, bool& paused) {
    if (event.type == SDL_QUIT) {
        return true;
    }
    if (event.type != SDL_KEYDOWN) {
        return false;
    }
    const SDL_Keycode key = event.key.keysym.sym;
    switch (key) {
        case SDLK_ESCAPE:
        case SDLK_q:
            return true;
        case SDLK_p:
            paused = !paused;
            return false;
        case SDLK_r:
            // Перезапуск с тем же seed — партия остаётся воспроизводимой.
            game.reset(game.snapshot().seed);
            paused = false;
            return false;
        default:
            break;
    }

    if (paused || game.game_over()) {
        return false;
    }

    // Повторные SDL_KEYDOWN (event.key.repeat) дают удержание для стрелок.
    switch (key) {
        case SDLK_LEFT:
            game.apply(tetris::Action::Left);
            break;
        case SDLK_RIGHT:
            game.apply(tetris::Action::Right);
            break;
        case SDLK_UP:
        case SDLK_x:
            game.apply(tetris::Action::RotateCW);
            break;
        case SDLK_z:
            game.apply(tetris::Action::RotateCCW);
            break;
        case SDLK_a:
            game.apply(tetris::Action::Rotate180);
            break;
        case SDLK_DOWN:
            game.apply(tetris::Action::SoftDrop);
            break;
        case SDLK_SPACE:
            game.apply(tetris::Action::HardDrop);
            break;
        case SDLK_c:
        case SDLK_LSHIFT:
            game.apply(tetris::Action::Hold);
            break;
        default:
            break;
    }
    return false;
}

}  // namespace

namespace tetris {

int run_sdl(Game& game, const SdlConfig& config) {
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER) != 0) {
        std::cerr << "SDL_Init не удался: " << SDL_GetError() << "\n";
        return 1;
    }

    const Layout layout = make_layout(config);
    SDL_Window* window = SDL_CreateWindow("Tetris", SDL_WINDOWPOS_CENTERED,
                                          SDL_WINDOWPOS_CENTERED, layout.window_w,
                                          layout.window_h, SDL_WINDOW_SHOWN);
    if (window == nullptr) {
        std::cerr << "SDL_CreateWindow не удался: " << SDL_GetError() << "\n";
        SDL_Quit();
        return 1;
    }

    // Аппаратный рендерер, при неудаче — программный (без X-ускорения).
    SDL_Renderer* renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (renderer == nullptr) {
        renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
    }
    if (renderer == nullptr) {
        std::cerr << "SDL_CreateRenderer не удался: " << SDL_GetError() << "\n";
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);

    const int fps = config.fps > 0 ? config.fps : 60;
    const double frame_ms = 1000.0 / static_cast<double>(fps);

    bool running = true;
    bool paused = false;
    long long best = load_best_score();
    bool best_recorded = false;  // рекорд записывается один раз за партию
    double tick_accumulator = 0.0;
    Uint32 frame_start = SDL_GetTicks();

    while (running) {
        SDL_Event event;
        while (SDL_PollEvent(&event) != 0) {
            if (handle_event(event, game, paused)) {
                running = false;
            }
        }
        if (!running) {
            break;
        }

        const Uint32 now = SDL_GetTicks();
        const Uint32 delta = now - frame_start;
        frame_start = now;

        if (!paused && !game.game_over()) {
            tick_accumulator += static_cast<double>(delta);
            // Не более пяти тиков за кадр: после системного лага партия не «прыгает».
            int guard = 0;
            while (tick_accumulator >= frame_ms && guard < 5) {
                game.advance_ticks(1);  // ровно один тик ядра — вся логика в ядре
                tick_accumulator -= frame_ms;
                ++guard;
            }
            if (guard == 5) {
                tick_accumulator = 0.0;
            }
        } else {
            tick_accumulator = 0.0;
        }

        // Рекорд: обновляем файл, когда партия закончилась, и сбрасываем флаг после
        // перезапуска (R), чтобы новая партия снова могла его побить.
        if (game.game_over()) {
            if (!best_recorded) {
                const long long score = game.snapshot().score;
                if (score > best) {
                    best = score;
                    save_best_score(best);
                }
                best_recorded = true;
            }
        } else {
            best_recorded = false;
        }

        render_frame(renderer, game.snapshot(), layout, config, paused, best);

        const Uint32 elapsed = SDL_GetTicks() - now;
        if (elapsed < static_cast<Uint32>(frame_ms)) {
            SDL_Delay(static_cast<Uint32>(frame_ms) - elapsed);
        }
    }

    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}

}  // namespace tetris

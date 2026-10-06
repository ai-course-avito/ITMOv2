// Тесты ASCII-рендера (docs/spec.md, раздел 8, п.7).
#include "tetris/ui/ascii.hpp"

#include "tetris/core/game.hpp"

#include "test_framework.hpp"

#include <string>
#include <vector>

using namespace tetris;

namespace {

std::vector<std::string> split_lines(const std::string& text) {
    std::vector<std::string> lines;
    std::string current;
    for (char c : text) {
        if (c == '\n') {
            lines.push_back(current);
            current.clear();
        } else {
            current.push_back(c);
        }
    }
    if (!current.empty()) lines.push_back(current);
    return lines;
}

std::size_t count_char(const std::string& s, char c) {
    std::size_t n = 0;
    for (char ch : s) {
        if (ch == c) ++n;
    }
    return n;
}

const AsciiOptions kFieldOnly{false, false, false, false, false};

}  // namespace

TEST(ascii, field_only_is_twenty_lines_of_ten) {
    Game g(42);
    const std::vector<std::string> lines = split_lines(render_ascii(g.snapshot(), kFieldOnly));
    CHECK_EQ(lines.size(), static_cast<std::size_t>(20));
    for (const std::string& line : lines) {
        CHECK_EQ(line.size(), static_cast<std::size_t>(10));
    }
    CHECK_EQ(lines[0], std::string(".........."));  // строка 0 — верх поля
}

TEST(ascii, active_piece_is_drawn_uppercase) {
    Game g(5);  // I
    for (int i = 0; i < 25; ++i) g.apply(Action::SoftDrop);  // I ложится на дно
    GameSnapshot s = g.snapshot();
    const std::string a = render_ascii(s, AsciiOptions{true, false, false, false, false});
    CHECK_EQ(count_char(a, 'I'), static_cast<std::size_t>(4));
    // Активная фигура стоит на дне — символы в последней строке поля.
    const std::vector<std::string> lines = split_lines(a);
    CHECK(lines.back().find('I') != std::string::npos);
}

TEST(ascii, ghost_is_drawn_with_colon) {
    Game g(5);  // I в спавне: активная фигура в буфере, призрак — на дне
    const GameSnapshot s = g.snapshot();
    const std::string text = render_ascii(s, AsciiOptions{false, true, false, false, false});
    CHECK_EQ(count_char(text, ':'), static_cast<std::size_t>(4));
}

TEST(ascii, active_overrides_ghost_when_grounded) {
    Game g(5);
    for (int i = 0; i < 25; ++i) g.apply(Action::SoftDrop);
    const std::string text = render_ascii(g.snapshot(), AsciiOptions{true, true, false, false, false});
    CHECK_EQ(count_char(text, 'I'), static_cast<std::size_t>(4));
    CHECK_EQ(count_char(text, ':'), static_cast<std::size_t>(0));
}

TEST(ascii, frame_and_stats_are_added) {
    const GameSnapshot s = run_script(42, "L L HD", 20000);
    const std::string text = render_ascii(s, AsciiOptions{true, true, true, true, false});
    CHECK(text.find("TETRIS") != std::string::npos);
    CHECK(text.find('+') != std::string::npos);
    CHECK(text.find("Score:") != std::string::npos);
    CHECK(text.find("Next:") != std::string::npos);
}

TEST(ascii, colors_add_ansi_sequences) {
    Game g(5);
    for (int i = 0; i < 25; ++i) g.apply(Action::SoftDrop);
    const std::string text = render_ascii(g.snapshot(), AsciiOptions{true, false, false, false, true});
    CHECK(text.find("\033[") != std::string::npos);
}

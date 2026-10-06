// ASCII-рендер состояния (см. include/tetris/ui/ascii.hpp).
#include "tetris/ui/ascii.hpp"

#include <string>
#include <vector>

namespace tetris {

namespace {

// ANSI-цвет по типу фигуры (используется только при options.colors).
const char* color_code(PieceType t) {
    switch (t) {
        case PieceType::I: return "36";  // циан
        case PieceType::J: return "34";  // синий
        case PieceType::L: return "33";  // жёлтый
        case PieceType::O: return "33";
        case PieceType::S: return "32";  // зелёный
        case PieceType::T: return "35";  // пурпурный
        case PieceType::Z: return "31";  // красный
    }
    return "37";
}

std::string join_lines(const std::vector<std::string>& lines) {
    std::string out;
    for (const std::string& line : lines) {
        out += line;
        out.push_back('\n');
    }
    return out;
}

}  // namespace

std::string render_ascii(const GameSnapshot& snapshot, const AsciiOptions& options) {
    // Сетка символов видимого поля: строка 0 — верх (y = 19).
    std::vector<std::string> rows = snapshot.board.to_ascii(true);
    std::vector<std::vector<int>> color(static_cast<std::size_t>(Board::kVisibleHeight),
                                        std::vector<int>(static_cast<std::size_t>(Board::kWidth), 0));

    // Накладывает фигуру на сетку. color >= 0 включает ANSI-цвет, -1 — без цвета.
    const auto overlay = [&](Point origin, PieceType type, Rotation rotation, char glyph,
                             int color_index) {
        const Shape shape = piece_shape(type, rotation);
        for (const Point& c : shape) {
            const int x = origin.x + c.x;
            const int y = origin.y + c.y;
            if (x < 0 || x >= Board::kWidth || y < 0 || y >= Board::kVisibleHeight) {
                continue;
            }
            const std::size_t row = static_cast<std::size_t>(Board::kVisibleHeight - 1 - y);
            rows[row][static_cast<std::size_t>(x)] = glyph;
            color[row][static_cast<std::size_t>(x)] = color_index;
        }
    };

    // Сначала призрак, затем активная фигура — активная имеет приоритет.
    if (options.with_ghost && snapshot.ghost && snapshot.active) {
        overlay(*snapshot.ghost, snapshot.active->type, snapshot.active->rotation, ':', -1);
    }
    if (options.with_active && snapshot.active) {
        const int color_index = options.colors ? static_cast<int>(snapshot.active->type) : -1;
        overlay(snapshot.active->pos, snapshot.active->type, snapshot.active->rotation,
                piece_char(snapshot.active->type), color_index);
    }

    // Собираем строки поля, применяя цвета.
    std::vector<std::string> field;
    field.reserve(static_cast<std::size_t>(Board::kVisibleHeight));
    for (int r = 0; r < Board::kVisibleHeight; ++r) {
        std::string line;
        for (int x = 0; x < Board::kWidth; ++x) {
            const std::size_t ux = static_cast<std::size_t>(x);
            const std::size_t ur = static_cast<std::size_t>(r);
            const char glyph = rows[ur][ux];
            if (options.colors && color[ur][ux] >= 0) {
                line += "\033[";
                line += color_code(static_cast<PieceType>(color[ur][ux]));
                line += 'm';
                line.push_back(glyph);
                line += "\033[0m";
            } else {
                line.push_back(glyph);
            }
        }
        field.push_back(std::move(line));
    }

    std::vector<std::string> lines;
    if (options.with_frame) {
        lines.push_back("TETRIS");
        lines.push_back('+' + std::string(static_cast<std::size_t>(Board::kWidth), '-') + '+');
        for (const std::string& row : field) {
            lines.push_back('|' + row + '|');
        }
        lines.push_back('+' + std::string(static_cast<std::size_t>(Board::kWidth), '-') + '+');
    } else {
        lines = field;
    }

    if (options.with_stats) {
        lines.push_back("Score: " + std::to_string(snapshot.score));
        lines.push_back("Lines: " + std::to_string(snapshot.lines) +
                        "  Level: " + std::to_string(snapshot.level));
        std::string hold = "Hold: ";
        hold += snapshot.hold ? std::string(1, piece_char(*snapshot.hold)) : "-";
        lines.push_back(hold);
        std::string next = "Next:";
        for (PieceType t : snapshot.next) {
            next.push_back(' ');
            next.push_back(piece_char(t));
        }
        lines.push_back(next);
    }

    return join_lines(lines);
}

}  // namespace tetris

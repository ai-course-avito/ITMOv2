// JSON-сериализация состояния игры (docs/spec.md, раздел 6).
#include "tetris/core/serialize.hpp"

#include <sstream>
#include <string>

namespace tetris {

namespace {

std::string escape(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: out.push_back(c);
        }
    }
    return out;
}

}  // namespace

std::string hash_hex(std::uint64_t value) {
    static const char kHex[] = "0123456789abcdef";
    std::string out(16, '0');
    for (int i = 15; i >= 0; --i) {
        out[static_cast<std::size_t>(i)] = kHex[value & 0xFULL];
        value >>= 4;
    }
    return out;
}

std::string to_json(const GameSnapshot& snapshot, bool include_board) {
    std::ostringstream os;

    os << '{';
    os << "\"seed\":" << snapshot.seed << ',';
    os << "\"tick\":" << snapshot.tick << ',';
    os << "\"score\":" << snapshot.score << ',';
    os << "\"lines\":" << snapshot.lines << ',';
    os << "\"level\":" << snapshot.level << ',';
    os << "\"combo\":" << snapshot.combo << ',';
    os << "\"back_to_back\":" << (snapshot.back_to_back ? "true" : "false") << ',';
    os << "\"game_over\":" << (snapshot.game_over ? "true" : "false") << ',';

    os << "\"hold\":";
    if (snapshot.hold) {
        os << '"' << piece_char(*snapshot.hold) << '"';
    } else {
        os << "null";
    }
    os << ',';
    os << "\"hold_used\":" << (snapshot.hold_used ? "true" : "false") << ',';

    os << "\"active\":";
    if (snapshot.active) {
        const ActivePiece& p = *snapshot.active;
        os << "{\"type\":\"" << piece_char(p.type) << "\",\"rotation\":"
           << static_cast<int>(p.rotation) << ",\"x\":" << p.pos.x << ",\"y\":" << p.pos.y << '}';
    } else {
        os << "null";
    }
    os << ',';

    os << "\"ghost\":";
    if (snapshot.ghost) {
        os << "{\"x\":" << snapshot.ghost->x << ",\"y\":" << snapshot.ghost->y << '}';
    } else {
        os << "null";
    }
    os << ',';

    os << "\"next\":[";
    for (std::size_t i = 0; i < snapshot.next.size(); ++i) {
        if (i != 0) os << ',';
        os << '"' << piece_char(snapshot.next[i]) << '"';
    }
    os << "],";

    if (include_board) {
        const std::vector<std::string> rows = snapshot.board.to_ascii(true);
        os << "\"board\":{\"width\":" << Board::kWidth << ",\"height\":"
           << Board::kVisibleHeight << ",\"rows\":[";
        for (std::size_t i = 0; i < rows.size(); ++i) {
            if (i != 0) os << ',';
            os << '"' << rows[i] << '"';
        }
        os << "]},";
    }

    os << "\"board_hash\":\"" << hash_hex(snapshot.board.hash()) << "\",";
    os << "\"holes\":" << snapshot.holes << ',';

    os << "\"events\":[";
    for (std::size_t i = 0; i < snapshot.events.size(); ++i) {
        if (i != 0) os << ',';
        os << '"' << escape(snapshot.events[i]) << '"';
    }
    os << ']';

    os << '}';
    return os.str();
}

}  // namespace tetris

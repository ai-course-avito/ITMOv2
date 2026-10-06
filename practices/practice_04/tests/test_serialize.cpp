// Тесты JSON-сериализации (docs/spec.md, раздел 8, п.6 и раздел 6).
#include "tetris/core/serialize.hpp"

#include "test_framework.hpp"

#include <cctype>
#include <string>

using namespace tetris;

namespace {

std::size_t count_substring(const std::string& hay, const std::string& needle) {
    std::size_t count = 0;
    std::size_t pos = 0;
    while ((pos = hay.find(needle, pos)) != std::string::npos) {
        ++count;
        pos += needle.size();
    }
    return count;
}

std::size_t count_char(const std::string& s, char c) {
    std::size_t count = 0;
    for (char ch : s) {
        if (ch == c) ++count;
    }
    return count;
}

}  // namespace

TEST(serialize, contains_all_required_keys) {
    Game g(42);
    const std::string json = to_json(g.snapshot(), true);
    const char* keys[] = {"\"seed\"",  "\"tick\"",      "\"score\"",     "\"lines\"",
                          "\"level\"", "\"combo\"",     "\"back_to_back\"", "\"game_over\"",
                          "\"hold\"",  "\"hold_used\"", "\"active\"",    "\"ghost\"",
                          "\"next\"",  "\"board\"",     "\"board_hash\"", "\"holes\"",
                          "\"events\""};
    for (const char* key : keys) {
        CHECK(json.find(key) != std::string::npos);
    }
}

TEST(serialize, board_has_twenty_rows_of_ten_cells) {
    Game g(7);  // пустое поле в начале
    const std::string json = to_json(g.snapshot(), true);
    CHECK(json.find("\"width\":10") != std::string::npos);
    CHECK(json.find("\"height\":20") != std::string::npos);
    // Пустое поле — двадцать строк по десять точек.
    CHECK_EQ(count_substring(json, "\"..........\""), static_cast<std::size_t>(20));

    // Дополнительно: внутри массива rows ровно 20 открывающих кавычек.
    const std::size_t start = json.find("\"rows\":[");
    REQUIRE(start != std::string::npos);
    const std::size_t end = json.find(']', start);
    REQUIRE(end != std::string::npos);
    const std::string rows = json.substr(start, end - start);
    CHECK_EQ(count_char(rows, '"'), static_cast<std::size_t>(20 * 2 + 2));  // "rows" + 20 строк
}

TEST(serialize, delimiters_are_balanced) {
    const std::string json = to_json(run_script(42, "L L D HD R CW HD", 20000), true);
    CHECK_EQ(count_char(json, '{'), count_char(json, '}'));
    CHECK_EQ(count_char(json, '['), count_char(json, ']'));
    CHECK_EQ(count_char(json, '"') % 2, static_cast<std::size_t>(0));
}

TEST(serialize, no_board_keeps_hash) {
    const GameSnapshot s = run_script(5, "HD HD", 20000);
    const std::string with_board = to_json(s, true);
    const std::string without_board = to_json(s, false);
    CHECK(with_board.find("\"board\":") != std::string::npos);
    CHECK(without_board.find("\"board\":") == std::string::npos);
    CHECK(without_board.find("\"board_hash\":") != std::string::npos);
    // Хеш не зависит от включения массива поля.
    CHECK(with_board.find(hash_hex(s.board.hash())) != std::string::npos);
    CHECK(without_board.find(hash_hex(s.board.hash())) != std::string::npos);
}

TEST(serialize, hash_hex_is_sixteen_lowercase_hex_digits) {
    const std::string text = hash_hex(0x0123456789abcdefULL);
    CHECK_EQ(text.size(), static_cast<std::size_t>(16));
    CHECK_EQ(text, std::string("0123456789abcdef"));
    const std::string zero = hash_hex(0);
    CHECK_EQ(zero, std::string("0000000000000000"));
    for (char c : hash_hex(0xdeadbeefcafef00dULL)) {
        const bool hex = std::isdigit(static_cast<unsigned char>(c)) != 0 ||
                         (c >= 'a' && c <= 'f');
        CHECK(hex);
    }
}

TEST(serialize, absent_fields_are_null_or_empty) {
    const GameSnapshot empty{};
    const std::string json = to_json(empty, true);
    CHECK(json.find("\"hold\":null") != std::string::npos);
    CHECK(json.find("\"active\":null") != std::string::npos);
    CHECK(json.find("\"ghost\":null") != std::string::npos);
    CHECK(json.find("\"next\":[]") != std::string::npos);
    CHECK(json.find("\"events\":[]") != std::string::npos);
}

TEST(serialize, active_piece_and_next_are_serialized) {
    Game g(5);  // I
    const std::string json = to_json(g.snapshot(), true);
    CHECK(json.find("\"type\":\"I\"") != std::string::npos);
    CHECK(json.find("\"rotation\":0") != std::string::npos);
    CHECK(json.find("\"next\":[\"T\"") != std::string::npos);  // seed 5: после I идёт T
}

TEST(serialize, events_are_serialized) {
    const GameSnapshot s = run_script(3, "HD HD CW CW HD", 20000);
    const std::string json = to_json(s, true);
    CHECK(json.find("\"clear:tspin\"") != std::string::npos);
}

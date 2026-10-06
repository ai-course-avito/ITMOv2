// Тесты хранения рекорда (docs/spec.md, AC-3.3). Модуль без SDL, поэтому
// проверяется здесь, а не ручной игрой.
#include "tetris/ui/highscore.hpp"

#include "test_framework.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

using namespace tetris;

namespace {

// Рабочий каталог для тестов: подкаталог TMPDIR (не трогаем реальный рекорд игрока).
std::filesystem::path scratch_dir() {
    const std::filesystem::path dir =
        std::filesystem::temp_directory_path() / "tetris_highscore_tests";
    std::filesystem::create_directories(dir);
    return dir;
}

void write_text_file(const std::filesystem::path& path, const std::string& text) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::trunc);
    out << text;
}

}  // namespace

TEST(highscore, roundtrip) {
    const std::filesystem::path path = scratch_dir() / "roundtrip" / "highscore";
    std::filesystem::remove_all(path.parent_path());

    write_highscore(path.string(), 12345);
    CHECK_EQ(read_highscore(path.string()), 12345LL);

    write_highscore(path.string(), 7);
    CHECK_EQ(read_highscore(path.string()), 7LL);
}

TEST(highscore, write_creates_missing_directories) {
    const std::filesystem::path path = scratch_dir() / "deep" / "nested" / "dir" / "highscore";
    std::filesystem::remove_all(scratch_dir() / "deep");

    write_highscore(path.string(), 900);
    CHECK(std::filesystem::exists(path));
    CHECK_EQ(read_highscore(path.string()), 900LL);
}

TEST(highscore, missing_file_is_zero) {
    const std::filesystem::path path = scratch_dir() / "absent" / "highscore";
    std::filesystem::remove_all(path.parent_path());
    CHECK_EQ(read_highscore(path.string()), 0LL);
}

TEST(highscore, broken_and_negative_values_are_zero) {
    const std::filesystem::path garbage = scratch_dir() / "broken" / "highscore";
    write_text_file(garbage, "это не число\n");
    CHECK_EQ(read_highscore(garbage.string()), 0LL);

    const std::filesystem::path negative = scratch_dir() / "negative" / "highscore";
    write_text_file(negative, "-500\n");
    CHECK_EQ(read_highscore(negative.string()), 0LL);

    const std::filesystem::path empty = scratch_dir() / "empty" / "highscore";
    write_text_file(empty, "");
    CHECK_EQ(read_highscore(empty.string()), 0LL);
}

TEST(highscore, empty_path_is_silently_ignored) {
    CHECK_EQ(read_highscore(""), 0LL);
    write_highscore("", 100);  // не должно бросать и не должно ничего создать
    CHECK_EQ(read_highscore(""), 0LL);
}

TEST(highscore, default_path_follows_xdg_then_home) {
    const std::string saved_xdg = std::getenv("XDG_DATA_HOME") ? std::getenv("XDG_DATA_HOME") : "";
    const bool had_xdg = std::getenv("XDG_DATA_HOME") != nullptr;

    setenv("XDG_DATA_HOME", "/tmp/xdg_probe", 1);
    CHECK_EQ(default_highscore_path(), std::string("/tmp/xdg_probe/tetris/highscore"));

    unsetenv("XDG_DATA_HOME");
    const char* home = std::getenv("HOME");
    if (home != nullptr) {
        CHECK_EQ(default_highscore_path(), std::string(home) + "/.local/share/tetris/highscore");
    }

    // Возвращаем окружение в исходное состояние, чтобы не влиять на другие тесты.
    if (had_xdg) {
        setenv("XDG_DATA_HOME", saved_xdg.c_str(), 1);
    } else {
        unsetenv("XDG_DATA_HOME");
    }
    CHECK_EQ(default_highscore_path().empty(), false);
}

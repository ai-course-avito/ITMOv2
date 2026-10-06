// Реализация хранения рекорда (см. highscore.hpp). Ни SDL, ни вывода в stdout:
// модуль проверяется unit-тестами tests/test_highscore.cpp.
#include "tetris/ui/highscore.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <system_error>

namespace tetris {

std::string default_highscore_path() {
    const char* xdg = std::getenv("XDG_DATA_HOME");
    std::string base;
    if (xdg != nullptr && xdg[0] != '\0') {
        base = xdg;
    } else {
        const char* home = std::getenv("HOME");
        if (home == nullptr || home[0] == '\0') {
            return {};
        }
        base = std::string(home) + "/.local/share";
    }
    return base + "/tetris/highscore";
}

long long read_highscore(const std::string& path) {
    if (path.empty()) {
        return 0;
    }
    std::ifstream in(path);
    long long value = 0;
    if (!(in >> value) || value < 0) {
        return 0;
    }
    return value;
}

void write_highscore(const std::string& path, long long score) {
    if (path.empty()) {
        return;
    }
    std::error_code ec;
    std::filesystem::create_directories(std::filesystem::path(path).parent_path(), ec);
    std::ofstream out(path, std::ios::trunc);
    if (!out) {
        return;
    }
    out << score << "\n";
}

}  // namespace tetris

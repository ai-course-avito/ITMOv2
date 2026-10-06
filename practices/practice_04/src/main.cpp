// Точка входа CLI (контракт — docs/spec.md, раздел 5).
//
// Здесь нет ни строчки игровой логики: headless-прогон целиком делегируется
// ядру через run_script(), печать — через to_json()/render_ascii(). Без
// --headless тот же Game отдаётся SDL-фронтенду. Собирается без SDL:
// заголовок sdl_app.hpp не тянет SDL2 (он виден только sdl_app.cpp), поэтому
// headless-режим работает в системах без видео.
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

#include "tetris/core/game.hpp"
#include "tetris/core/serialize.hpp"
#include "tetris/ui/ascii.hpp"
#include "tetris/ui/sdl_app.hpp"

namespace {

// Разобранные аргументы командной строки.
struct Options {
    bool headless{false};
    std::uint64_t seed{0};
    std::string script{};
    int max_ticks{20000};
    bool ascii{false};
    bool json{false};   // явный --json; в headless JSON и так режим по умолчанию
    bool no_board{false};
};

void print_usage(std::ostream& out) {
    out << "Использование:\n"
           "  tetris [--headless] [--seed N] [--script \"TOKENS\"] [--ticks N]\n"
           "         [--json|--ascii] [--no-board] [--help]\n"
           "\n"
           "Режимы:\n"
           "  --headless        без SDL: выполнить сценарий и напечатать результат\n"
           "  (по умолчанию)    открыть окно SDL2\n"
           "\n"
           "Параметры:\n"
           "  --seed N          seed генератора фигур, целое >= 0 (по умолчанию 0)\n"
           "  --script TOKENS   сценарий ввода; токены через пробел или запятую:\n"
           "                    L R CW CCW 180 D HD HOLD T\n"
           "                    суффикс-число повторяет токен: D3, T120, L2\n"
           "  --ticks N         максимум тиков симуляции (по умолчанию 20000)\n"
           "  --json            печатать JSON (режим по умолчанию в headless)\n"
           "  --ascii           печатать поле в ASCII\n"
           "  --no-board        не включать массив board в JSON (board_hash остаётся)\n"
           "  --help            эта справка\n"
           "\n"
           "Коды выхода: 0 — прогон выполнен (в т.ч. при game over),\n"
           "             1 — ошибка инициализации SDL, 2 — ошибка аргументов.\n";
}

// Строго беззнаковое целое: пустая строка, знаки и мусор считаются ошибкой.
bool parse_u64(const std::string& text, std::uint64_t& out) {
    if (text.empty()) {
        return false;
    }
    std::uint64_t value = 0;
    for (const char c : text) {
        if (c < '0' || c > '9') {
            return false;
        }
        const std::uint64_t digit = static_cast<std::uint64_t>(c - '0');
        if (value > (UINT64_MAX - digit) / 10ULL) {  // переполнение
            return false;
        }
        value = value * 10ULL + digit;
    }
    out = value;
    return true;
}

// Сообщение об ошибке аргументов; возвращаемый код — 2 (docs/spec.md, раздел 5).
int argument_error(const std::string& message) {
    std::cerr << "tetris: " << message << "\n";
    std::cerr << "Подсказка: tetris --help\n";
    return 2;
}

int run_cli(int argc, char** argv) {
    Options options;

    // --help обрабатывается раньше любого разбора: справка не должна падать
    // из-за того, что рядом стоит некорректный флаг.
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            print_usage(std::cout);
            return 0;
        }
    }

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        std::string inline_value;
        bool has_inline_value = false;
        // Поддерживаем и "--seed 42", и "--seed=42".
        const std::size_t eq = arg.find('=');
        if (arg.rfind("--", 0) == 0 && eq != std::string::npos) {
            inline_value = arg.substr(eq + 1);
            arg = arg.substr(0, eq);
            has_inline_value = true;
        }

        // Достаёт значение флага из "=value" либо из следующего аргумента.
        const auto take_value = [&](std::string& destination) -> bool {
            if (has_inline_value) {
                destination = inline_value;
                return true;
            }
            if (i + 1 >= argc) {
                return false;
            }
            destination = argv[++i];
            return true;
        };

        if (arg == "--headless" || arg == "--json" || arg == "--ascii" ||
            arg == "--no-board") {
            if (has_inline_value) {
                return argument_error(arg + " не принимает значение");
            }
            if (arg == "--headless") {
                options.headless = true;
            } else if (arg == "--json") {
                options.json = true;
            } else if (arg == "--ascii") {
                options.ascii = true;
            } else {
                options.no_board = true;
            }
        } else if (arg == "--seed") {
            std::string value;
            if (!take_value(value)) {
                return argument_error("--seed требует значение");
            }
            if (!parse_u64(value, options.seed)) {
                return argument_error("--seed: ожидается целое >= 0, получено \"" + value + "\"");
            }
        } else if (arg == "--script") {
            if (!take_value(options.script)) {
                return argument_error("--script требует значение");
            }
        } else if (arg == "--ticks") {
            std::string value;
            if (!take_value(value)) {
                return argument_error("--ticks требует значение");
            }
            std::uint64_t parsed = 0;
            if (!parse_u64(value, parsed) || parsed > 2147483647ULL) {
                return argument_error("--ticks: ожидается целое 0.." +
                                      std::to_string(2147483647) + ", получено \"" + value + "\"");
            }
            options.max_ticks = static_cast<int>(parsed);
        } else if (arg == "--help" || arg == "-h") {
            print_usage(std::cout);
            return 0;
        } else {
            return argument_error("неизвестный аргумент: " + std::string(argv[i]));
        }
    }

    if (options.json && options.ascii) {
        return argument_error("--json и --ascii взаимоисключающие");
    }

    // Неизвестный токен сценария — ошибка аргументов, а не тихое «ничего не делать»:
    // агент не должен получать успешный прогон с незамеченной опечаткой в сценарии.
    for (const std::string& token : tetris::split_script(options.script)) {
        if (!tetris::action_from_token(token)) {
            return argument_error("неизвестный токен сценария: \"" + token +
                                  "\" (см. --help, раздел --script)");
        }
    }

    if (!options.headless) {
        // Интерактивный режим: окно, ввод и отрисовка — в sdl_app.cpp.
        tetris::Game game(options.seed);
        const tetris::SdlConfig config{};
        return tetris::run_sdl(game, config);
    }

    const tetris::GameSnapshot snapshot =
        tetris::run_script(options.seed, options.script, options.max_ticks);

    if (options.ascii) {
        const tetris::AsciiOptions ascii_options{};
        std::cout << tetris::render_ascii(snapshot, ascii_options) << "\n";
    } else {
        std::cout << tetris::to_json(snapshot, !options.no_board) << "\n";
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    return run_cli(argc, argv);
}

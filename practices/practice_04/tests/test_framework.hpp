// Минимальный тест-фреймворк: без внешних зависимостей, header-only.
// Тесты пишутся как TEST(suite, name) { ... CHECK(...); } и собираются в один
// бинарник вместе с tests/main.cpp.
#pragma once

#include <cmath>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace testfw {

struct TestCase {
    std::string suite;
    std::string name;
    std::function<void()> fn;
};

inline std::vector<TestCase>& registry() {
    static std::vector<TestCase> cases;
    return cases;
}

struct Registrar {
    Registrar(const char* suite, const char* name, std::function<void()> fn) {
        registry().push_back(TestCase{suite, name, std::move(fn)});
    }
};

struct Failure {
    std::string message;
    bool fatal{false};
};

inline int& failures() {
    static int count = 0;
    return count;
}

inline int& checks() {
    static int count = 0;
    return count;
}

inline std::string& current_test() {
    static std::string name;
    return name;
}

// Печатает сообщение о провалившейся проверке; при fatal бросает исключение,
// чтобы прекратить текущий тест.
inline void report_failure(const std::string& file, int line, const std::string& text) {
    ++failures();
    std::cerr << "    FAIL " << current_test() << " " << file << ":" << line << ": " << text << "\n";
}

inline void fail_now(const std::string& file, int line, const std::string& text) {
    report_failure(file, line, text);
    throw Failure{text, true};
}

inline int run_all() {
    int failed_tests = 0;
    std::size_t passed = 0;
    for (const auto& tc : registry()) {
        current_test() = tc.suite + "." + tc.name;
        const int before = failures();
        try {
            tc.fn();
        } catch (const Failure&) {
            // Уже зарегистрировано.
        } catch (const std::exception& e) {
            report_failure("<unknown>", 0, std::string("uncaught exception: ") + e.what());
        } catch (...) {
            report_failure("<unknown>", 0, "uncaught non-std exception");
        }
        if (failures() == before) {
            ++passed;
        } else {
            ++failed_tests;
            std::cerr << "  [FAIL] " << current_test() << "\n";
        }
    }
    std::cout << "\n" << passed << "/" << registry().size() << " tests passed, "
              << checks() << " checks, " << failures() << " failures\n";
    return failed_tests == 0 ? 0 : 1;
}

}  // namespace testfw

#define TESTFW_CONCAT2(a, b) a##b
#define TESTFW_CONCAT(a, b) TESTFW_CONCAT2(a, b)

#define TEST(suite, name)                                                                    \
    static void TESTFW_CONCAT(tetris_test_, __LINE__)();                                     \
    static ::testfw::Registrar TESTFW_CONCAT(tetris_registrar_, __LINE__)(                   \
        #suite, #name, &TESTFW_CONCAT(tetris_test_, __LINE__));                              \
    static void TESTFW_CONCAT(tetris_test_, __LINE__)()

#define CHECK(cond)                                                                          \
    do {                                                                                     \
        ++::testfw::checks();                                                                \
        if (!(cond)) {                                                                       \
            ::testfw::report_failure(__FILE__, __LINE__, "CHECK(" #cond ")");                \
        }                                                                                    \
    } while (false)

#define REQUIRE(cond)                                                                        \
    do {                                                                                     \
        ++::testfw::checks();                                                                \
        if (!(cond)) {                                                                       \
            ::testfw::fail_now(__FILE__, __LINE__, "REQUIRE(" #cond ")");                    \
        }                                                                                    \
    } while (false)

#define CHECK_FALSE(cond) CHECK(!(cond))

#define CHECK_EQ(a, b)                                                                       \
    do {                                                                                     \
        ++::testfw::checks();                                                                \
        const auto& lhs_ = (a);                                                              \
        const auto& rhs_ = (b);                                                              \
        if (!(lhs_ == rhs_)) {                                                               \
            std::ostringstream oss_;                                                         \
            oss_ << "CHECK_EQ(" #a ", " #b ") — left=" << lhs_ << " right=" << rhs_;         \
            ::testfw::report_failure(__FILE__, __LINE__, oss_.str());                        \
        }                                                                                    \
    } while (false)

#define CHECK_NEAR(a, b, eps)                                                                \
    do {                                                                                     \
        ++::testfw::checks();                                                                \
        const double lhs_ = static_cast<double>(a);                                           \
        const double rhs_ = static_cast<double>(b);                                           \
        if (std::fabs(lhs_ - rhs_) > (eps)) {                                                \
            std::ostringstream oss_;                                                         \
            oss_ << "CHECK_NEAR(" #a ", " #b ") — left=" << lhs_ << " right=" << rhs_;        \
            ::testfw::report_failure(__FILE__, __LINE__, oss_.str());                        \
        }                                                                                    \
    } while (false)

#define FAIL_TEST(msg) ::testfw::fail_now(__FILE__, __LINE__, (msg))

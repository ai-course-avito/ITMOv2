cmake_minimum_required(VERSION 3.20)

# Проект практики 4: ядро Tetris (C++20) + headless-CLI + SDL2-фронтенд.
# Ядро и тесты не зависят от SDL; SDL нужен только цели tetris.
project(tetris LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Тип сборки" FORCE)
endif()

add_compile_options(-Wall -Wextra -Wpedantic)

# --- SDL2 через pkg-config --------------------------------------------------
# Ищем только для цели tetris; tetris_tests собирается без SDL.
find_package(PkgConfig REQUIRED)
pkg_check_modules(SDL2 REQUIRED sdl2)

# --- Источники --------------------------------------------------------------
# src/core/*.cpp и tests/*.cpp дописываются параллельно, поэтому используем
# GLOB с CONFIGURE_DEPENDS: конфигурация не падает на пустом списке, а новые
# файлы подхватываются при следующей сборке без ручного перезапуска cmake.
file(GLOB_RECURSE TETRIS_CORE_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/core/*.cpp")
file(GLOB_RECURSE TETRIS_TEST_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tests/*.cpp")

# --- Исполняемый файл игры (SDL2) -------------------------------------------
add_executable(tetris
    src/main.cpp
    src/ui/sdl_app.cpp
    src/ui/ascii.cpp
    src/ui/highscore.cpp
    ${TETRIS_CORE_SOURCES}
)
target_include_directories(tetris PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    ${SDL2_INCLUDE_DIRS}
)
target_compile_options(tetris PRIVATE ${SDL2_CFLAGS_OTHER})
target_link_libraries(tetris PRIVATE ${SDL2_LIBRARIES})
target_link_directories(tetris PRIVATE ${SDL2_LIBRARY_DIRS})

# --- Тесты (headless, без SDL) ----------------------------------------------
add_executable(tetris_tests
    ${TETRIS_TEST_SOURCES}
    src/ui/ascii.cpp
    src/ui/highscore.cpp
    ${TETRIS_CORE_SOURCES}
)
target_include_directories(tetris_tests PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests"
)

# --- Регистрация ctest ------------------------------------------------------
enable_testing()
add_test(NAME core COMMAND tetris_tests)

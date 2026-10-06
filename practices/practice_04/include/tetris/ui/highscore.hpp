// Хранение рекорда (docs/spec.md, AC-3.3). Модуль намеренно не зависит от SDL:
// так его можно покрыть обычными unit-тестами, а не только ручной игрой.
#pragma once

#include <string>

namespace tetris {

// Путь к файлу рекорда: $XDG_DATA_HOME/tetris/highscore, иначе
// $HOME/.local/share/tetris/highscore. Пустая строка — нет обеих переменных.
std::string default_highscore_path();

// Чтение рекорда. Отсутствующий, пустой, битый файл или отрицательное значение
// дают 0: недоступное хранилище не должно ронять игру.
long long read_highscore(const std::string& path);

// Запись рекорда с созданием каталогов. Любая ошибка файловой системы игнорируется
// (игра продолжается без рекорда).
void write_highscore(const std::string& path, long long score);

}  // namespace tetris

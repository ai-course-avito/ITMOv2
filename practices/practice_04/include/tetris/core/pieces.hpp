// Формы фигур для каждого состояния поворота и таблицы вылетов SRS.
#pragma once

#include <vector>

#include "tetris/core/types.hpp"

namespace tetris {

// Занятые клетки фигуры в данном состоянии поворота, в координатах бокса 4x4.
Shape piece_shape(PieceType t, Rotation r);

// Таблица вылетов SRS для перехода from -> to (соседние состояния поворота).
// Для O-фигуры таблица пуста: вращение O всегда удаётся без вылета.
// Порядок смещений — как в guideline: сначала (0,0), затем остальные четыре.
const std::vector<Point>& srs_kicks(PieceType t, Rotation from, Rotation to);

}  // namespace tetris

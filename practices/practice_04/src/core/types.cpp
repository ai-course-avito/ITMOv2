// Реализация базовых функций по типу фигуры (см. include/tetris/core/types.hpp).
#include "tetris/core/types.hpp"

namespace tetris {

char piece_char(PieceType t) {
    // Символ совпадает с первой буквой имени типа и используется в ASCII/JSON.
    switch (t) {
        case PieceType::I: return 'I';
        case PieceType::J: return 'J';
        case PieceType::L: return 'L';
        case PieceType::O: return 'O';
        case PieceType::S: return 'S';
        case PieceType::T: return 'T';
        case PieceType::Z: return 'Z';
    }
    return '?';
}

const char* piece_name(PieceType t) {
    switch (t) {
        case PieceType::I: return "I";
        case PieceType::J: return "J";
        case PieceType::L: return "L";
        case PieceType::O: return "O";
        case PieceType::S: return "S";
        case PieceType::T: return "T";
        case PieceType::Z: return "Z";
    }
    return "?";
}

std::optional<PieceType> piece_from_char(char c) {
    switch (c) {
        case 'I': case 'i': return PieceType::I;
        case 'J': case 'j': return PieceType::J;
        case 'L': case 'l': return PieceType::L;
        case 'O': case 'o': return PieceType::O;
        case 'S': case 's': return PieceType::S;
        case 'T': case 't': return PieceType::T;
        case 'Z': case 'z': return PieceType::Z;
        default: return std::nullopt;
    }
}

}  // namespace tetris

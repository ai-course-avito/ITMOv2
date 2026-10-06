// Генератор фигур «7-bag» с детерминированным ГПСЧ (xorshift64*).
#pragma once

#include <array>
#include <cstdint>
#include <vector>

#include "tetris/core/types.hpp"

namespace tetris {

class PieceBag {
public:
    // seed == 0 заменяется на 0x9E3779B97F4A7C15, чтобы нулевое состояние было валидным.
    explicit PieceBag(std::uint64_t seed = 0);

    // Полный сброс генератора: новая перестановка мешка из семи фигур.
    void reseed(std::uint64_t seed);

    // Следующая фигура: мешок из всех семи типов, перемешанный Фишером—Йетсом.
    PieceType next();

    // Заглянуть на n фигур вперёд, не меняя состояние (n >= 1).
    std::vector<PieceType> peek(int n);

    std::uint64_t seed() const { return seed_; }
    std::uint64_t state() const { return state_; }

private:
    std::uint32_t next_u32();
    void refill();

    std::uint64_t seed_{0};
    std::uint64_t state_{0};
    std::array<PieceType, kPieceTypeCount> bag_{};
    int bag_pos_{kPieceTypeCount};
    std::vector<PieceType> future_{};  // буфер для peek()
};

}  // namespace tetris

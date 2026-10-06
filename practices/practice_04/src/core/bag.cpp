// Реализация «7-bag» на детерминированном xorshift64* (см. bag.hpp).
#include "tetris/core/bag.hpp"

namespace tetris {

namespace {
// Ненулевое значение подставляется вместо seed == 0: у xorshift нулевое
// состояние вырождается в константу.
constexpr std::uint64_t kDefaultSeed = 0x9E3779B97F4A7C15ULL;
}  // namespace

PieceBag::PieceBag(std::uint64_t seed) {
    reseed(seed);
}

void PieceBag::reseed(std::uint64_t seed) {
    seed_ = (seed == 0) ? kDefaultSeed : seed;
    state_ = seed_;
    bag_pos_ = kPieceTypeCount;  // пустой мешок: первый next() замешивает новый
    future_.clear();
    for (int i = 0; i < kPieceTypeCount; ++i) {
        bag_[static_cast<std::size_t>(i)] = static_cast<PieceType>(i);
    }
}

std::uint32_t PieceBag::next_u32() {
    // xorshift64*: сдвиги 12/25/27, затем умножение на магическую константу.
    std::uint64_t x = state_;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    state_ = x;
    const std::uint64_t mixed = x * 0x2545F4914F6CDD1DULL;
    return static_cast<std::uint32_t>(mixed >> 32);
}

void PieceBag::refill() {
    // Мешок из всех семи типов, перемешанный Фишером—Йетсом.
    bag_pos_ = 0;
    for (int i = kPieceTypeCount - 1; i > 0; --i) {
        const int j = static_cast<int>(next_u32() % static_cast<std::uint32_t>(i + 1));
        const PieceType tmp = bag_[static_cast<std::size_t>(i)];
        bag_[static_cast<std::size_t>(i)] = bag_[static_cast<std::size_t>(j)];
        bag_[static_cast<std::size_t>(j)] = tmp;
    }
}

PieceType PieceBag::next() {
    if (bag_pos_ >= kPieceTypeCount) {
        refill();
    }
    return bag_[static_cast<std::size_t>(bag_pos_++)];
}

std::vector<PieceType> PieceBag::peek(int n) {
    if (n < 1) {
        n = 1;
    }
    // Заглядываем вперёд на копии состояния и восстановливаем его — peek не
    // меняет ни счётчик, ни ГПСЧ.
    const std::uint64_t saved_state = state_;
    const std::array<PieceType, kPieceTypeCount> saved_bag = bag_;
    const int saved_pos = bag_pos_;

    std::vector<PieceType> out;
    out.reserve(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        out.push_back(next());
    }

    state_ = saved_state;
    bag_ = saved_bag;
    bag_pos_ = saved_pos;
    return out;
}

}  // namespace tetris

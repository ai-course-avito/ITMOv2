// Тесты генератора фигур «7-bag» (docs/spec.md, раздел 8, п.1).
#include "tetris/core/bag.hpp"

#include "test_framework.hpp"

#include <algorithm>
#include <set>
#include <vector>

using namespace tetris;

namespace {

std::vector<PieceType> draw(PieceBag& bag, int n) {
    std::vector<PieceType> out;
    for (int i = 0; i < n; ++i) out.push_back(bag.next());
    return out;
}

}  // namespace

TEST(bag, first_seven_are_all_types) {
    PieceBag bag(1234);
    const std::vector<PieceType> seq = draw(bag, 7);
    std::set<int> seen;
    for (PieceType t : seq) seen.insert(piece_index(t));
    CHECK_EQ(static_cast<int>(seen.size()), 7);
    for (int i = 0; i < kPieceTypeCount; ++i) {
        CHECK(seen.count(i) == 1);
    }
}

TEST(bag, second_bag_also_has_all_types) {
    PieceBag bag(99);
    draw(bag, 7);
    const std::vector<PieceType> second = draw(bag, 7);
    std::set<int> seen;
    for (PieceType t : second) seen.insert(piece_index(t));
    CHECK_EQ(static_cast<int>(seen.size()), 7);
}

TEST(bag, same_seed_same_sequence) {
    PieceBag a(42);
    PieceBag b(42);
    const std::vector<PieceType> seq_a = draw(a, 25);
    const std::vector<PieceType> seq_b = draw(b, 25);
    CHECK(seq_a == seq_b);
}

TEST(bag, different_seed_differs) {
    PieceBag a(1);
    PieceBag b(2);
    const std::vector<PieceType> seq_a = draw(a, 30);
    const std::vector<PieceType> seq_b = draw(b, 30);
    CHECK(seq_a != seq_b);
}

TEST(bag, zero_seed_is_valid_and_deterministic) {
    PieceBag a(0);
    PieceBag b(0);
    CHECK(a.seed() != 0);
    CHECK(a.seed() == b.seed());
    CHECK(draw(a, 14) == draw(b, 14));
}

TEST(bag, peek_does_not_mutate_state) {
    PieceBag bag(7);
    const std::uint64_t state_before = bag.state();
    const std::uint64_t seed_before = bag.seed();
    const std::vector<PieceType> lookahead = bag.peek(10);
    CHECK_EQ(lookahead.size(), static_cast<std::size_t>(10));
    CHECK_EQ(bag.state(), state_before);
    CHECK_EQ(bag.seed(), seed_before);
    // После peek реальные выдачи совпадают с подсмотренными.
    const std::vector<PieceType> actual = draw(bag, 10);
    CHECK(actual == lookahead);
}

TEST(bag, peek_matches_future_draws_of_twin_bag) {
    PieceBag observed(2024);
    PieceBag twin(2024);
    const std::vector<PieceType> lookahead = observed.peek(12);
    const std::vector<PieceType> future = draw(twin, 12);
    CHECK(lookahead == future);
}

TEST(bag, peek_across_bag_boundary) {
    // peek(10) должен корректно переходить в следующий мешок.
    PieceBag observed(555);
    PieceBag twin(555);
    const std::vector<PieceType> lookahead = observed.peek(10);
    const std::vector<PieceType> future = draw(twin, 10);
    CHECK(lookahead == future);
    CHECK(draw(observed, 10) == future);
}

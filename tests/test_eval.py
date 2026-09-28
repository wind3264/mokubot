from eval import evaluate
from tests.positions import position


def test_empty_board_is_even():
    assert evaluate(position([], [])) == 0


def test_own_open_three_on_move_beats_opponent_open_three():
    three = [(7, 6), (7, 7), (7, 8)]
    far = [(2, 2)]
    good = evaluate(position(three, far + [(3, 3)], black_to_move=True))
    bad = evaluate(position(far + [(3, 3), (3, 4)], three, black_to_move=True))
    assert good > 0 > bad
    assert good > -bad  # tempo: my three on my move is worth more


def test_open_three_worth_more_than_closed_three():
    open3 = evaluate(position([(7, 6), (7, 7), (7, 8)], [(2, 2), (2, 4)]))
    closed3 = evaluate(position([(7, 6), (7, 7), (7, 8)], [(7, 5), (2, 2)]))
    assert open3 > closed3


def test_fork_penalty():
    # white has two open threes; black to move can only block one
    white = [(7, 6), (7, 7), (7, 8), (4, 2), (5, 2), (6, 2)]
    single = [(7, 6), (7, 7), (7, 8), (2, 10), (4, 12), (0, 5)]
    black = [(1, 1), (1, 3), (3, 1), (3, 3), (1, 5), (5, 5), (10, 10)]
    fork = evaluate(position(black, white))
    one = evaluate(position(black, single))
    assert fork < one - 10000


def test_blocking_reduces_opponent_score():
    before = evaluate(position([(2, 2), (2, 4)], [(7, 6), (7, 7), (7, 8)]))
    after = evaluate(position([(2, 2), (2, 4), (7, 9)], [(7, 6), (7, 7), (7, 8), (12, 7)]))
    assert after > before

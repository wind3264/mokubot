import pytest

from minimax import MATE_BOUND, Engine
from tests.positions import position


def best(board, **kw):
    kw.setdefault("time_limit", 5)
    kw.setdefault("max_depth", 4)
    e = Engine()
    return e.best_move(board, time_limit=kw["time_limit"], max_depth=kw["max_depth"]), e


def test_takes_the_win():
    b = position([(7, 3), (7, 4), (7, 5), (7, 6)], [(8, 3), (8, 4), (8, 5), (0, 0)])
    move, _ = best(b)
    assert move in [(7, 2), (7, 7)]


def test_blocks_a_four():
    b = position([(7, 3), (7, 4), (7, 5), (7, 6), (3, 10)], [(7, 2), (9, 9), (9, 11), (11, 9)],
                 black_to_move=False)
    move, _ = best(b)
    assert move == (7, 7)


def test_wins_before_blocking():
    # both sides have a four; the side to move just wins
    b = position([(7, 3), (7, 4), (7, 5), (7, 6), (0, 14)], [(9, 3), (9, 4), (9, 5), (9, 6), (7, 2)],
                 black_to_move=False)
    move, _ = best(b)
    assert move in [(9, 2), (9, 7)]


def test_answers_an_open_three():
    b = position([(7, 6), (7, 7), (7, 8), (3, 3)], [(2, 12), (4, 12), (3, 10)], black_to_move=False)
    move, _ = best(b)
    assert move in [(7, 5), (7, 9), (7, 4), (7, 10)]


def test_makes_a_double_four():
    # (7, 6) completes a four on the row and on the column at once
    black = [(7, 3), (7, 4), (7, 5), (4, 6), (5, 6), (6, 6)]
    white = [(7, 2), (3, 6), (0, 0), (0, 14), (14, 0), (14, 14)]
    b = position(black, white)
    move, e = best(b)
    assert move == (7, 6)
    assert e.info["score"] > MATE_BOUND


def test_prevents_a_double_four():
    black = [(7, 3), (7, 4), (7, 5), (4, 6), (5, 6), (6, 6)]
    white = [(7, 2), (3, 6), (0, 0), (0, 14), (14, 0)]
    b = position(black, white, black_to_move=False)
    move, _ = best(b)
    assert move == (7, 6)


def test_finds_a_long_vcf():
    # black has no immediate double four but wins with a chain of fours
    black = [(7, 3), (7, 4), (7, 5), (4, 6), (5, 6), (10, 9), (11, 9), (12, 9)]
    white = [(7, 2), (3, 6), (9, 9), (0, 0), (0, 14), (14, 14), (14, 0)]
    b = position(black, white)
    e = Engine()
    e.board = b
    e.root_len = len(b.moves)
    e.nodes = 0
    e.deadline = float("inf")
    assert e.vcf_search(1) is None
    assert e.vcf_search(10) is not None
    # the vcf must actually win against every forced reply
    assert plays_out(b, e)


def plays_out(b, e):
    # follow the vcf: attacker plays the vcf move, defender blocks
    for _ in range(30):
        me = b.side
        cells = b.win_cells(me)
        if cells:
            return True
        m = e.vcf_search(10)
        if m is None:
            return False
        b.play(m)
        replies = b.win_cells(me)
        if len(replies) >= 2:
            return True
        b.play(replies[0])
    return False


def test_no_vcf_in_quiet_position():
    b = position([(7, 7), (8, 8)], [(7, 8), (6, 6)])
    e = Engine()
    e.board = b
    e.nodes = 0
    e.deadline = float("inf")
    assert e.vcf_search(10) is None


@pytest.mark.parametrize("black_to_move", [True, False])
def test_search_restores_board(black_to_move):
    b = position([(7, 7), (8, 8), (6, 9)], [(7, 8), (6, 6)], black_to_move)
    snapshot = (list(b.cells), b.hash, [list(c) for c in b.counts[1:]], list(b.moves))
    Engine().best_move(b, time_limit=0.3)
    assert (list(b.cells), b.hash, [list(c) for c in b.counts[1:]], list(b.moves)) == snapshot


def test_finds_a_double_three_by_vct():
    # (7, 8) makes a broken three on the row and an open three on the column
    black = [(7, 5), (7, 6), (5, 8), (6, 8)]
    white = [(0, 0), (0, 14), (14, 0), (14, 14)]
    b = position(black, white)
    e = Engine()
    e.board = b
    e.nodes = 0
    e.deadline = float("inf")
    e.vct_limit = float("inf")
    assert e.vcf_search(10) is None
    assert e.vct_attack(4) is not None
    move, e = best(b)
    assert e.info.get("vct")


def test_vcf_is_bounded_on_a_crowded_board():
    # many closed threes for both sides: the unbounded search can take minutes
    import random
    from game import Board
    rng = random.Random(3)
    b = Board()
    while len(b.moves) < 110:
        b.play(rng.choice(b.candidates()))
        if b.last_move_won():
            b.unplay()
            b.unplay()
    e = Engine()
    e.board = b
    e.nodes = 0
    e.deadline = float("inf")
    moves = list(b.moves)
    e.vcf(30, 500)
    assert e.nodes <= 501
    assert b.moves == moves

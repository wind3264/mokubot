import random

import pytest

from game import (BLACK, LINE_CELLS, LINE_LEN, NLINES, SIZE, WHITE, ZOBRIST,
                  ZOBRIST_SIDE, Board, perft)
from patterns import NSHAPES, line_info


def board_from(moves):
    b = Board()
    for m in moves:
        b.make_move(m)
    return b


def five(cells):
    # interleave the given black cells with harmless white replies
    moves = []
    white = [(14, 2 * k) for k in range(len(cells))]
    for k, c in enumerate(cells):
        moves.append(c)
        if k < len(cells) - 1:
            moves.append(white[k])
    return moves


def test_empty_board():
    b = Board()
    assert b.get_result() == "ongoing"
    assert len(b.get_legal_moves()) == 225
    assert b.get_candidate_moves() == [(7, 7)]
    assert b.black_to_move


def test_illegal_moves():
    b = Board()
    b.make_move((7, 7))
    with pytest.raises(ValueError):
        b.make_move((7, 7))
    with pytest.raises(ValueError):
        b.make_move((15, 0))
    with pytest.raises(ValueError):
        b.make_move((0, -1))
    with pytest.raises(RuntimeError):
        Board().undo_move()


@pytest.mark.parametrize("cells", [
    [(0, k) for k in range(5)],                      # top edge
    [(k, 0) for k in range(5)],                      # left edge
    [(k, k) for k in range(5)],                      # corner diagonal
    [(14 - k, k) for k in range(10, 15)],            # anti-diagonal into a corner
    [(k, 14 - k) for k in range(5)],                 # anti-diagonal from top right
    [(9 + k, 10 + k) for k in range(5)],             # diagonal into the right edge
    [(7, 3), (7, 4), (7, 6), (7, 7), (7, 5)],        # completed in the middle
])
def test_win_detection(cells):
    b = board_from(five(cells))
    assert b.check_win(cells[-1])
    assert b.get_result() == "black wins"
    assert b.is_game_over()
    assert b.get_legal_moves() == []


def test_four_is_not_a_win():
    b = board_from(five([(7, k) for k in range(4)]))
    assert b.get_result() == "ongoing"


def test_overline_wins():
    # freestyle rules: six in a row counts
    cells = [(7, 2), (7, 3), (7, 4), (7, 6), (7, 7), (7, 5)]
    b = board_from(five(cells))
    assert b.get_result() == "black wins"


def test_blocked_by_edge_or_opponent_is_not_five():
    b = board_from([(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2), (0, 3), (0, 4)])
    # white stone on (0, 4) breaks black's row
    assert b.get_result() == "ongoing"


def test_white_wins():
    moves = [(14, 14), (7, 0), (14, 12), (7, 1), (14, 10), (7, 2), (14, 8), (7, 3), (13, 0), (7, 4)]
    b = board_from(moves)
    assert b.get_result() == "white wins"


def test_draw():
    # stripes of two, offset by two per row, never line up five in any direction
    b = Board()
    order = [(i, j) for i in range(SIZE) for j in range(SIZE)]
    blacks = [(i, j) for i, j in order if (j + 2 * i) // 2 % 2 == 0]
    whites = [(i, j) for i, j in order if (j + 2 * i) // 2 % 2 == 1]
    assert len(blacks) == len(whites) + 1
    for k in range(SIZE * SIZE):
        b.make_move(blacks[k // 2] if k % 2 == 0 else whites[k // 2])
        assert b.get_result() in ("ongoing", "draw")
    assert b.check_draw()
    assert b.get_result() == "draw"


def recount(b):
    counts = [None, [0] * NSHAPES, [0] * NSHAPES]
    for lid in range(NLINES):
        key = sum(b.cells[idx] * 3 ** pos for pos, idx in enumerate(LINE_CELLS[lid]))
        assert key == b.line_keys[lid]
        shapes = line_info(key, LINE_LEN[lid])[0]
        for c in (1, 2):
            for s in shapes[c]:
                counts[c][s] += 1
    return counts


def test_incremental_state_matches_recomputation():
    rng = random.Random(1)
    for _ in range(20):
        b = Board()
        while not b.is_game_over() and len(b.moves) < 120:
            b.make_move(rng.choice(b.get_legal_moves() if rng.random() < 0.2 else b.get_candidate_moves()))
            assert b.counts == recount(b)
            h = 0
            for idx, c in enumerate(b.cells):
                if c:
                    h ^= ZOBRIST[c][idx]
            if len(b.moves) % 2:
                h ^= ZOBRIST_SIDE
            assert h == b.hash
            for i in range(SIZE):
                for j in range(SIZE):
                    assert b.board[i][j] == b.cells[i * SIZE + j]
        while b.moves:
            b.undo_move()
        assert b.counts == recount(b) == [None, [0] * NSHAPES, [0] * NSHAPES]
        assert b.hash == 0
        assert not any(b.near)
        assert b.black_to_move


def test_perft_empty_board():
    b = Board()
    assert perft(b, 1) == 225
    assert perft(b, 2) == 225 * 224
    assert perft(b, 1, candidates_only=True) == 1
    assert perft(b, 2, candidates_only=True) == 24
    # second stone at offset (dx, dy): the two 5x5 boxes overlap in
    # (5 - |dx|)(5 - |dy|) cells, so the sum of (50 - overlap - 2) over the
    # 24 offsets is 24 * 48 - (19 ** 2 - 25)
    assert perft(b, 3, candidates_only=True) == 816


def test_perft_counts_finished_games_as_leaves():
    # black to move can win at (7, 4) or (7, 9); each of those ends the game
    b = board_from(five([(7, 5), (7, 6), (7, 7), (7, 8)]) + [(0, 0)])
    legal = len(b.get_legal_moves())
    assert perft(b, 2) == 2 + (legal - 2) * (legal - 1)


def test_candidates_are_near_stones():
    b = board_from([(0, 0)])
    assert sorted(b.get_candidate_moves()) == sorted(
        (i, j) for i in range(3) for j in range(3) if (i, j) != (0, 0))

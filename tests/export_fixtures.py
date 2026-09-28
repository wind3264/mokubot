# writes web/test/fixtures.json: positions with the python engine's answers,
# which the javascript port must reproduce exactly
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eval import evaluate  # noqa: E402
from game import SIZE, Board  # noqa: E402
from minimax import Engine, VctLimit  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "web", "test", "fixtures.json")


def random_position(rng, n):
    b = Board()
    while len(b.moves) < n:
        cands = b.candidates()
        # prefer cells next to many stones so real shapes appear
        cands.sort(key=lambda idx: -b.near[idx])
        b.play(rng.choice(cands[:max(3, len(cands) // 3)]))
        if b.last_move_won():
            b.unplay()
            b.unplay()
    return b


def played_position(rng, n):
    # a position from a quick engine game, so quieter than random stones
    b = Board()
    for _ in range(3):
        b.play(rng.choice([idx for idx in range(SIZE * SIZE) if b.cells[idx] == 0
                           and abs(idx // SIZE - 7) <= 3 and abs(idx % SIZE - 7) <= 3]))
    e = Engine()
    while len(b.moves) < n:
        b.play(e.iterative_deepening(b, 1e9, 1))
        if b.last_move_won():
            b.unplay()
            break
    return b


def engine_at(b):
    e = Engine()
    e.board = b
    e.nodes = 0
    e.deadline = float("inf")
    e.root_len = len(b.moves)
    return e


def main():
    rng = random.Random(7)
    cases = []
    for k in range(80):
        if k % 2:
            b = random_position(rng, rng.randrange(4, 60))
        else:
            b = played_position(rng, rng.randrange(4, 40))
        e = engine_at(b)
        me = b.side
        case = {
            "moves": [i * SIZE + j for i, j in b.moves],
            "counts": [b.counts[1], b.counts[2]],
            "eval": evaluate(b),
            "win_cells": [b.win_cells(1), b.win_cells(2)],
            "four_cells": [b.four_cells(1), b.four_cells(2)],
            "order_root": e.order_moves(root=True),
            "order": e.order_moves(),
            "vcf": e.vcf_search(10),
        }
        e = engine_at(b)
        e.vct_limit = 20000
        try:
            case["vct"] = e.vct_attack(4)
        except VctLimit:
            case["vct"] = "limit"
            while len(b.moves) > e.root_len:
                b.unplay()
        depth = 4 if k < 10 else 3 if k < 40 else 2
        case["depth"] = depth
        searcher = Engine()
        case["best"] = searcher.iterative_deepening(b, 1e9, depth)
        case["info"] = searcher.info
        assert b.side == me
        cases.append(case)
    with open(OUT, "w") as f:
        json.dump(cases, f)
    print(f"wrote {len(cases)} cases")


if __name__ == "__main__":
    main()

# uses heuristics to evaluate the current boardstate
# heuristic is counting the number of:
# 1. open 4 or 5 in a row = auto win
# 2. other 4 = opponent forced to respond, win in 1 otherwise
# 3. open 3, broken 3 = opponent forced to respond, win in 2 otherwise
#
# fives and fours never reach evaluate(): the search resolves them exactly
# (win now, lose to two win cells, or forced block). what is left is scored
# as a weighted count of shapes from the point of view of the side to move.
# the side to move and its opponent get separate weights because tempo is
# everything here: my three on my move is a winning threat, the opponent's
# three on my move is something i have to spend this move answering.
from patterns import ONE, CLOSED_TWO, TWO, CLOSED_THREE, THREE, OPEN_THREE

directions = [(1, 0), (0, 1), (1, 1), (1, -1)]

# gets a line of radius 4 (so total length 9) with the given starting cell and direction
def get_line(board, cell, direction):
    i, j = cell
    di, dj = direction
    cells = []
    for k in range(-4, 5):
        x, y = i + k * di, j + k * dj
        if 0 <= x < 15 and 0 <= y < 15:
            cells.append(board[x][y])
        else:
            cells.append(-1)
    return cells


SCORED_SHAPES = [ONE, CLOSED_TWO, TWO, CLOSED_THREE, THREE, OPEN_THREE]

# parameter vector tuned by tune.py:
#   0-5   own shape weights (side to move), in SCORED_SHAPES order
#   6-11  opponent shape weights
#   12    bonus when the side to move has any three (it can make an open four)
#   13    penalty when the opponent has two or more threes (a fork)
WEIGHT_NAMES = (["own_" + n for n in ("one", "closed_two", "two", "closed_three", "three", "open_three")]
                + ["opp_" + n for n in ("one", "closed_two", "two", "closed_three", "three", "open_three")]
                + ["own_threat", "opp_fork"])

DEFAULT_WEIGHTS = [
    10, 50, 100, 150, 800, 1000,
    12, 58, 115, 172, 920, 1150,
    5000, 20000,
]


def evaluate(board, weights=DEFAULT_WEIGHTS):
    me = board.side
    own = board.counts[me]
    opp = board.counts[3 - me]
    score = 0
    for k, s in enumerate(SCORED_SHAPES):
        score += weights[k] * own[s] - weights[k + 6] * opp[s]
    if own[THREE] + own[OPEN_THREE]:
        score += weights[12]
    if opp[THREE] + opp[OPEN_THREE] >= 2:
        score -= weights[13]
    return score

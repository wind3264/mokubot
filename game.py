# freestyle gomoku on a 15x15 board: five or more in a row wins for either
# color (overlines count) and there are no opening restrictions
import random

from patterns import (CLOSED_THREE, FIVE, FOUR, NSHAPES, OPEN_FOUR, OPEN_THREE,
                      POW3, THREE, line_info)

SIZE = 15
EMPTY, BLACK, WHITE = 0, 1, 2
DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1)]
CANDIDATE_RADIUS = 2


def _in_bounds(i, j):
    return 0 <= i < SIZE and 0 <= j < SIZE


def _build_lines():
    # every line of the board long enough to hold a five
    lines = []
    for di, dj in DIRECTIONS:
        for i in range(SIZE):
            for j in range(SIZE):
                if _in_bounds(i - di, j - dj):
                    continue  # not the first cell of its line
                cells = []
                x, y = i, j
                while _in_bounds(x, y):
                    cells.append(x * SIZE + y)
                    x, y = x + di, y + dj
                if len(cells) >= 5:
                    lines.append(cells)
    return lines


LINE_CELLS = _build_lines()
LINE_LEN = [len(cells) for cells in LINE_CELLS]
NLINES = len(LINE_CELLS)

# for each cell, (line id, position in line, 3 ** position) of every line through it
CELL_LINES = [[] for _ in range(SIZE * SIZE)]
for _lid, _cells in enumerate(LINE_CELLS):
    for _pos, _idx in enumerate(_cells):
        CELL_LINES[_idx].append((_lid, _pos, POW3[_pos]))

NEIGHBORS = []
for _idx in range(SIZE * SIZE):
    _i, _j = divmod(_idx, SIZE)
    NEIGHBORS.append([x * SIZE + y
                      for x in range(_i - CANDIDATE_RADIUS, _i + CANDIDATE_RADIUS + 1)
                      for y in range(_j - CANDIDATE_RADIUS, _j + CANDIDATE_RADIUS + 1)
                      if _in_bounds(x, y) and (x, y) != (_i, _j)])

_rng = random.Random(20250818)
ZOBRIST = [None, [_rng.getrandbits(64) for _ in range(SIZE * SIZE)],
           [_rng.getrandbits(64) for _ in range(SIZE * SIZE)]]
ZOBRIST_SIDE = _rng.getrandbits(64)

CENTER = (SIZE // 2) * SIZE + SIZE // 2


class Board:

    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [[EMPTY] * SIZE for _ in range(SIZE)]
        # 0 means empty, 1 means black, 2 means white. black goes first
        self.cells = [EMPTY] * (SIZE * SIZE)  # flat copy of board for the engine
        self.black_to_move = True
        self.moves = []  # stack to track move history
        self.line_keys = [0] * NLINES
        self.line_infos = [line_info(0, n) for n in LINE_LEN]  # line_info of each line
        # counts[color][shape] = number of line segments of that shape
        self.counts = [None, [0] * NSHAPES, [0] * NSHAPES]
        self.near = [0] * (SIZE * SIZE)  # stones within CANDIDATE_RADIUS
        self.hash = 0

    init_board = reset

    @property
    def side(self):
        return BLACK if self.black_to_move else WHITE

    # ---- rules ----

    def is_in_bounds(self, cell):
        return _in_bounds(*cell)

    def is_empty(self, cell):
        i, j = cell
        return self.board[i][j] == EMPTY

    def is_legal_move(self, cell):
        return self.is_in_bounds(cell) and self.is_empty(cell) and not self.is_game_over()

    def make_move(self, cell):
        if not self.is_legal_move(cell):
            raise ValueError("invalid move")
        i, j = cell
        self.play(i * SIZE + j)

    def undo_move(self):
        if len(self.moves) == 0:
            raise RuntimeError("no move to undo")
        self.unplay()

    def get_legal_moves(self):
        if self.is_game_over():
            return []
        return [divmod(idx, SIZE) for idx in range(SIZE * SIZE) if self.cells[idx] == EMPTY]

    def get_candidate_moves(self):
        return [divmod(idx, SIZE) for idx in self.candidates()]

    def check_win(self, last_move):
        i, j = last_move
        cur_player = self.board[i][j]
        if cur_player == EMPTY:
            return False
        for di, dj in DIRECTIONS:
            run = 1
            for sign in (1, -1):
                x, y = i + sign * di, j + sign * dj
                while _in_bounds(x, y) and self.board[x][y] == cur_player:
                    run += 1
                    x, y = x + sign * di, y + sign * dj
            if run >= 5:
                return True
        return False

    def check_draw(self):
        return len(self.moves) == SIZE * SIZE and not self.check_win(self.moves[-1])

    def is_game_over(self):
        return self.get_result() != "ongoing"

    def get_result(self):
        if len(self.moves) == 0:
            return "ongoing"
        if self.check_win(self.moves[-1]):
            return "white wins" if self.black_to_move else "black wins"
        if len(self.moves) == SIZE * SIZE:
            return "draw"
        return "ongoing"

    # ---- engine interface: flat cell indices, no legality checks ----

    def play(self, idx):
        color = BLACK if self.black_to_move else WHITE
        self._update_lines(idx, color)
        i, j = divmod(idx, SIZE)
        self.board[i][j] = color
        self.cells[idx] = color
        self.hash ^= ZOBRIST[color][idx] ^ ZOBRIST_SIDE
        near = self.near
        for n in NEIGHBORS[idx]:
            near[n] += 1
        self.black_to_move = not self.black_to_move
        self.moves.append((i, j))

    def unplay(self):
        i, j = self.moves.pop()
        idx = i * SIZE + j
        color = self.cells[idx]
        self._update_lines(idx, -color)
        self.board[i][j] = EMPTY
        self.cells[idx] = EMPTY
        self.hash ^= ZOBRIST[color][idx] ^ ZOBRIST_SIDE
        near = self.near
        for n in NEIGHBORS[idx]:
            near[n] -= 1
        self.black_to_move = not self.black_to_move

    def _update_lines(self, idx, delta):
        keys = self.line_keys
        infos = self.line_infos
        black, white = self.counts[1], self.counts[2]
        for lid, _, p in CELL_LINES[idx]:
            new = keys[lid] + delta * p
            keys[lid] = new
            before = infos[lid][0]
            info = infos[lid] = line_info(new, LINE_LEN[lid])
            after = info[0]
            for s in before[1]:
                black[s] -= 1
            for s in before[2]:
                white[s] -= 1
            for s in after[1]:
                black[s] += 1
            for s in after[2]:
                white[s] += 1

    def last_move_won(self):
        # the player who just moved made five
        return self.counts[3 - self.side][FIVE] > 0

    def has_four(self, color):
        c = self.counts[color]
        return c[FOUR] + c[OPEN_FOUR] > 0

    def win_cells(self, color):
        # empty cells where color would complete five, in ascending order
        if not self.has_four(color):
            return []
        return self._line_points(color, 1)

    def four_cells(self, color):
        # empty cells where color would make a new four, in ascending order
        c = self.counts[color]
        if not (c[CLOSED_THREE] + c[THREE] + c[OPEN_THREE] + c[FOUR] + c[OPEN_FOUR]):
            return []
        return self._line_points(color, 2)

    def _line_points(self, color, which):
        found = set()
        for lid, info in enumerate(self.line_infos):
            points = info[which][color]
            if points:
                cells = LINE_CELLS[lid]
                pos = 0
                while points:
                    if points & 1:
                        found.add(cells[pos])
                    points >>= 1
                    pos += 1
        return sorted(found)

    def candidates(self):
        # empty cells near a stone; the center on an empty board
        if not self.moves:
            return [CENTER]
        cells, near = self.cells, self.near
        return [idx for idx in range(SIZE * SIZE) if near[idx] and cells[idx] == EMPTY]

    # ---- debugging ----

    def print_board(self):
        print(self.to_string())

    def to_string(self):
        symbols = ".XO"
        last = self.moves[-1] if self.moves else None
        rows = ["   " + " ".join("abcdefghijklmno"[j] for j in range(SIZE))]
        for i in range(SIZE):
            row = []
            for j in range(SIZE):
                s = symbols[self.board[i][j]]
                row.append(s.lower() if (i, j) == last and s != "." else s)
            rows.append(f"{SIZE - i:2d} " + " ".join(row))
        return "\n".join(rows)

    @classmethod
    def from_string(cls, text):
        # build a position from rows of '.', 'X', 'O'; stones are placed
        # alternately (black first) so the side to move is consistent
        rows = [r.split() if " " in r.strip() else list(r.strip())
                for r in text.strip().splitlines()]
        blacks = [(i, j) for i, r in enumerate(rows) for j, s in enumerate(r) if s in "Xx"]
        whites = [(i, j) for i, r in enumerate(rows) for j, s in enumerate(r) if s in "Oo"]
        if not (len(blacks) == len(whites) or len(blacks) == len(whites) + 1):
            raise ValueError("stone counts do not alternate")
        b = cls()
        for k in range(len(blacks) + len(whites)):
            i, j = blacks[k // 2] if k % 2 == 0 else whites[k // 2]
            b.play(i * SIZE + j)
        return b


def perft(board, depth, candidates_only=False):
    """Number of move sequences of the given length from this position.

    Games that end early count as a single leaf. With candidates_only the
    restricted move generator used by the search is counted instead.
    """
    if depth == 0 or board.is_game_over():
        return 1
    if candidates_only:
        moves = board.candidates()
    else:
        moves = [i * SIZE + j for i, j in board.get_legal_moves()]
    if depth == 1:
        return len(moves)
    total = 0
    for idx in moves:
        board.play(idx)
        total += perft(board, depth - 1, candidates_only)
        board.unplay()
    return total

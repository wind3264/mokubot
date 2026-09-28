# alpha-beta search (negamax form) with iterative deepening, a zobrist-keyed
# transposition table, threat-aware move generation and VCF threat search
import time

from eval import DEFAULT_WEIGHTS, evaluate
from game import CELL_LINES, LINE_LEN, SIZE
from patterns import CLOSED_THREE, OPEN_THREE, POW3, THREE, line_info

MATE = 1_000_000_000
MATE_BOUND = MATE - 10_000  # scores beyond this are forced wins or losses
VCF_WIN = MATE - 5_000      # leaf VCF wins rank below exact short mates
# node budgets for VCF: on crowded boards the number of four sequences can
# explode, so an unfinished VCF counts as no VCF found
ROOT_VCF_NODES = 20_000
VCF_NODES = 1_000
INF = MATE + 1

EXACT, LOWER, UPPER = 0, 1, 2

# move ordering value of each shape, indexed by shape id
ORDER_VALUE = [0, 1, 4, 12, 20, 60, 90, 250, 2000, 10000]

_summary_cache = {}


def line_summary(key, length):
    """(value, threes, wins) per color for ordering and threat checks."""
    ck = key * 16 + length
    s = _summary_cache.get(ck)
    if s is None:
        shapes, wins, _ = line_info(key, length)
        s = [None, None, None]
        for c in (1, 2):
            s[c] = (sum(ORDER_VALUE[x] for x in shapes[c]),
                    sum(1 for x in shapes[c] if x == THREE or x == OPEN_THREE),
                    wins[c])
        _summary_cache[ck] = s
    return s


_table_cache = {}


def move_table(key, length):
    """What a stone at each empty position of the line would do.

    Returns (gain, blocks, four, three), each indexed [color][pos]: the
    ordering value color gains, the opponent threes it breaks, whether it
    gives color a five point and whether it gives color a new three.
    """
    ck = key * 16 + length
    t = _table_cache.get(ck)
    if t is None:
        before = line_summary(key, length)
        t = ([None, [0] * length, [0] * length], [None, [0] * length, [0] * length],
             [None, [0] * length, [0] * length], [None, [0] * length, [0] * length])
        rest = key
        for pos in range(length):
            if rest % 3 == 0:
                for c in (1, 2):
                    after = line_summary(key + c * POW3[pos], length)
                    t[0][c][pos] = after[c][0] - before[c][0]
                    t[1][c][pos] = before[3 - c][1] - after[3 - c][1]
                    t[2][c][pos] = 1 if after[c][2] else 0
                    t[3][c][pos] = 1 if after[c][1] > before[c][1] else 0
            rest //= 3
        _table_cache[ck] = t
    return t


class Timeout(Exception):
    pass


class VctLimit(Exception):
    pass


class VcfLimit(Exception):
    pass


def _mate_to_tt(score, ply):
    if score > MATE_BOUND:
        return score + ply
    if score < -MATE_BOUND:
        return score - ply
    return score


def _mate_from_tt(score, ply):
    if score > MATE_BOUND:
        return score - ply
    if score < -MATE_BOUND:
        return score + ply
    return score


class Engine:

    def __init__(self, weights=DEFAULT_WEIGHTS, max_depth=64, time_limit=2.0,
                 beam=12, vcf_depth=10, leaf_vcf=True, vct_depth=4, vct_nodes=20000):
        self.weights = weights
        self.max_depth = max_depth
        self.time_limit = time_limit
        self.beam = beam
        self.vcf_depth = vcf_depth
        self.leaf_vcf = leaf_vcf
        self.vct_depth = vct_depth
        self.vct_nodes = vct_nodes
        self.vct_fail = {}
        self.tt = {}
        self.vcf_fail = {}
        self.vcf_left = float("inf")

    # ---- public ----

    def best_move(self, board, time_limit=None, max_depth=None):
        """Best move for the side to move as (row, col)."""
        idx = self.iterative_deepening(board,
                                       self.time_limit if time_limit is None else time_limit,
                                       self.max_depth if max_depth is None else max_depth)
        return divmod(idx, SIZE)

    def iterative_deepening(self, board, time_budget, max_depth):
        self.board = board
        self.nodes = 0
        self.deadline = time.perf_counter() + time_budget
        self.start = time.perf_counter()
        self.info = {"depth": 0, "score": 0, "nodes": 0}
        self.root_len = len(board.moves)
        if len(self.tt) > 2_000_000:
            self.tt.clear()
        if len(self.vcf_fail) > 500_000:
            self.vcf_fail.clear()
        if len(self.vct_fail) > 500_000:
            self.vct_fail.clear()

        me = board.side
        op = 3 - me
        mine = board.win_cells(me)
        if mine:
            self.info["score"] = MATE - 1
            return mine[0]
        theirs = board.win_cells(op)
        if theirs:
            return theirs[0]  # forced (or lost anyway if there are several)
        moves = self.order_moves(root=True)
        best = moves[0]
        if len(moves) == 1:
            return best
        try:
            win = self.vcf(self.vcf_depth * 2, ROOT_VCF_NODES)
            if win is not None:
                self.info["score"] = VCF_WIN
                return win
            if self.vct_depth:
                # bounded by nodes rather than time so results do not depend on speed
                self.vct_limit = self.nodes + self.vct_nodes
                vct = None
                try:
                    vct = self.vct_attack(self.vct_depth)
                except VctLimit:
                    while len(board.moves) > self.root_len:
                        board.unplay()
                if vct is not None:
                    self.info["score"] = VCF_WIN
                    self.info["vct"] = True
                    return vct
            for depth in range(1, max_depth + 1):
                best_score, best_move = -INF, None
                alpha = -INF
                scored = []
                for k, m in enumerate(moves):
                    board.play(m)
                    if k == 0:
                        score = -self.search(depth - 1, -INF, -alpha, 1)
                    else:
                        score = -self.search(depth - 1, -alpha - 1, -alpha, 1)
                        if score > alpha:
                            score = -self.search(depth - 1, -INF, -alpha, 1)
                    board.unplay()
                    scored.append((score, k, m))
                    if score > best_score:
                        best_score, best_move = score, m
                        alpha = max(alpha, score)
                        best = m  # first move is the previous best, so any change is an improvement
                scored.sort(key=lambda t: (-t[0], t[1]))
                moves = [m for _, _, m in scored]
                self.info.update(depth=depth, score=best_score)
                if abs(best_score) > MATE_BOUND:
                    break
                if time.perf_counter() - self.start > time_budget * 0.4:
                    break
        except Timeout:
            while len(board.moves) > self.root_len:
                board.unplay()
        self.info["nodes"] = self.nodes
        return best

    # ---- search ----

    def search(self, depth, alpha, beta, ply):
        board = self.board
        self.nodes += 1
        if self.nodes & 1023 == 0 and time.perf_counter() > self.deadline:
            raise Timeout
        me = board.side
        op = 3 - me
        if board.has_four(me):
            return MATE - ply
        threats = board.win_cells(op)
        if len(threats) >= 2:
            return -(MATE - ply - 1)

        alpha0 = alpha
        entry = self.tt.get(board.hash)
        tt_move = None
        if entry is not None:
            e_depth, e_flag, e_score, tt_move = entry
            if e_depth >= depth:
                e_score = _mate_from_tt(e_score, ply)
                if e_flag == EXACT:
                    return e_score
                if e_flag == LOWER and e_score >= beta:
                    return e_score
                if e_flag == UPPER and e_score <= alpha:
                    return e_score

        if threats:
            moves = threats
            child_depth = depth  # forced replies do not use up depth
        elif depth <= 0:
            if self.leaf_vcf and self._has_four_moves(me) and self.vcf(self.vcf_depth, VCF_NODES) is not None:
                return VCF_WIN - ply
            return evaluate(board, self.weights)
        else:
            moves = self.order_moves(tt_move=tt_move)
            child_depth = depth - 1

        best_score, best_move = -INF, moves[0]
        for k, m in enumerate(moves):
            board.play(m)
            if k == 0:
                score = -self.search(child_depth, -beta, -alpha, ply + 1)
            else:
                score = -self.search(child_depth, -alpha - 1, -alpha, ply + 1)
                if alpha < score < beta:
                    score = -self.search(child_depth, -beta, -alpha, ply + 1)
            board.unplay()
            if score > best_score:
                best_score, best_move = score, m
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break

        flag = UPPER if best_score <= alpha0 else LOWER if best_score >= beta else EXACT
        self.tt[board.hash] = (depth, flag, _mate_to_tt(best_score, ply), best_move)
        return best_score

    def order_moves(self, tt_move=None, root=False):
        """Candidate moves, strongest first, trimmed to the beam width.

        A move is scored by what it builds for the side to move plus what
        the opponent would build on the same cell. If the opponent has a
        three, only moves that break it or make a four are kept.
        """
        board = self.board
        me = board.side
        op = 3 - me
        keys = board.line_keys
        op_threes = board.counts[op][THREE] + board.counts[op][OPEN_THREE]
        scored = []
        rest = []
        for idx in board.candidates():
            gain = 0
            blocked = 0
            makes_four = False
            for lid, pos, _ in CELL_LINES[idx]:
                gain_t, blocks_t, four_t, _ = move_table(keys[lid], LINE_LEN[lid])
                gain += gain_t[me][pos] + gain_t[op][pos]
                blocked += blocks_t[me][pos]
                if four_t[me][pos]:
                    makes_four = True
            if op_threes and not blocked and not makes_four:
                rest.append((gain, idx))
            else:
                scored.append((gain, idx))
        if not scored:
            scored = rest
        scored.sort(key=lambda t: (-t[0], t[1]))
        moves = [idx for _, idx in scored]
        if not root:
            moves = moves[:self.beam]
        if tt_move is not None and tt_move in moves:
            moves.remove(tt_move)
            moves.insert(0, tt_move)
        return moves

    # ---- threat space search ----

    def _has_four_moves(self, color):
        c = self.board.counts[color]
        return c[CLOSED_THREE] + c[THREE] + c[OPEN_THREE] > 0

    def four_moves(self, color):
        """Cells where color makes a four, best first."""
        board = self.board
        keys = board.line_keys
        found = []
        for idx in board.four_cells(color):
            gain = 0
            for lid, pos, _ in CELL_LINES[idx]:
                gain += move_table(keys[lid], LINE_LEN[lid])[0][color][pos]
            found.append((gain, idx))
        found.sort(key=lambda t: (-t[0], t[1]))
        return [idx for _, idx in found]

    def vcf(self, depth, budget):
        """vcf_search limited to budget nodes; None if the budget runs out."""
        board = self.board
        start = len(board.moves)
        self.vcf_left = budget
        try:
            return self.vcf_search(depth)
        except VcfLimit:
            while len(board.moves) > start:
                board.unplay()
            return None
        finally:
            self.vcf_left = float("inf")

    def vcf_search(self, depth):
        """A first move of a victory by continuous fours for the side to
        move, or None. depth is the number of attacking moves allowed."""
        board = self.board
        me = board.side
        op = 3 - me
        mine = board.win_cells(me)
        if mine:
            return mine[0]
        if depth <= 0:
            return None
        threats = board.win_cells(op)
        if len(threats) >= 2:
            return None
        known = self.vcf_fail.get(board.hash)
        if known is not None and known >= depth:
            return None
        if threats:
            moves = [m for m in threats if m in self.four_moves(me)]
        else:
            moves = self.four_moves(me)
        for m in moves:
            self.nodes += 1
            if self.nodes & 1023 == 0 and time.perf_counter() > self.deadline:
                raise Timeout
            self.vcf_left -= 1
            if self.vcf_left < 0:
                raise VcfLimit
            board.play(m)
            wins = board.win_cells(me)
            if len(wins) >= 2:
                board.unplay()
                return m
            board.play(wins[0])
            found = self.vcf_search(depth - 1) is not None
            board.unplay()
            board.unplay()
            if found:
                return m
        self.vcf_fail[board.hash] = depth
        return None

    # ---- victory by continuous threats ----
    # the attacker (side to move) plays fours and threes; the defender must
    # answer every three with a block or a counter four

    def vct_attack(self, depth):
        """First move of a win by continuous threats, or None."""
        board = self.board
        me = board.side
        op = 3 - me
        mine = board.win_cells(me)
        if mine:
            return mine[0]
        threats = board.win_cells(op)
        if len(threats) >= 2:
            return None
        if threats:
            board.play(threats[0])
            ok = self.vct_defend(depth)
            board.unplay()
            return threats[0] if ok else None
        vcf = self.vcf(self.vcf_depth, VCF_NODES)
        if vcf is not None:
            return vcf
        if depth <= 0:
            return None
        known = self.vct_fail.get(board.hash)
        if known is not None and known >= depth:
            return None
        for m in self.threat_moves(me):
            self.nodes += 1
            if self.nodes > self.vct_limit:
                raise VctLimit
            board.play(m)
            ok = self.vct_defend(depth - 1)
            board.unplay()
            if ok:
                return m
        self.vct_fail[board.hash] = depth
        return None

    def vct_defend(self, depth):
        """Defender to move against pending threats: True if every defense loses."""
        board = self.board
        me = board.side
        att = 3 - me
        if board.has_four(me):
            return False
        wins = board.win_cells(att)
        if len(wins) >= 2:
            return True
        if wins:
            defenses = wins
        else:
            c = board.counts[att]
            if not (c[THREE] + c[OPEN_THREE]):
                return False
            defenses = self.defense_moves(me)
        for d in defenses:
            self.nodes += 1
            if self.nodes > self.vct_limit:
                raise VctLimit
            board.play(d)
            lost = self.vct_attack(depth) is not None
            board.unplay()
            if not lost:
                return False
        return True

    def threat_moves(self, color):
        """Cells where color makes a four or a new three, best first."""
        board = self.board
        keys = board.line_keys
        found = []
        for idx in board.candidates():
            gain = 0
            threat = False
            for lid, pos, _ in CELL_LINES[idx]:
                gain_t, _, four_t, three_t = move_table(keys[lid], LINE_LEN[lid])
                gain += gain_t[color][pos]
                if four_t[color][pos] or three_t[color][pos]:
                    threat = True
            if threat:
                found.append((gain, idx))
        found.sort(key=lambda t: (-t[0], t[1]))
        return [idx for _, idx in found]

    def defense_moves(self, color):
        """Cells where color breaks an opponent three or makes a four."""
        board = self.board
        keys = board.line_keys
        out = []
        for idx in board.candidates():
            for lid, pos, _ in CELL_LINES[idx]:
                _, blocks_t, four_t, _ = move_table(keys[lid], LINE_LEN[lid])
                if blocks_t[color][pos] > 0 or four_t[color][pos]:
                    out.append(idx)
                    break
        return out

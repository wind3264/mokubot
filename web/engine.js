// javascript port of the python engine (patterns.py, game.py, eval.py,
// minimax.py). it mirrors the python move for move so the two can be checked
// against each other: see web/test/parity.test.mjs

export const SIZE = 15;
export const EMPTY = 0, BLACK = 1, WHITE = 2;

// ---- patterns ----

export const NONE = 0, ONE = 1, CLOSED_TWO = 2, TWO = 3, CLOSED_THREE = 4, THREE = 5,
  OPEN_THREE = 6, FOUR = 7, OPEN_FOUR = 8, FIVE = 9;
const NSHAPES = 10;

function popcount(x) {
  let n = 0;
  while (x) { x &= x - 1; n++; }
  return n;
}

function hasFive(mask) {
  return (mask & (mask >> 1) & (mask >> 2) & (mask >> 3) & (mask >> 4)) !== 0;
}

function fivePoints(mask, length) {
  let points = 0;
  for (let s = 0; s < length - 4; s++) {
    const w = (mask >> s) & 31;
    if (w !== 31 && popcount(w) === 4) points |= (~w & 31) << s;
  }
  return points;
}

function near(mask, length) {
  let n = mask;
  for (let d = 1; d < 5; d++) n |= (mask << d) | (mask >> d);
  return n & ~mask & ((1 << length) - 1);
}

function openFourPoints(mask, length) {
  let points = 0;
  for (let rest = near(mask, length); rest; rest &= rest - 1) {
    const b = rest & -rest;
    if (popcount(fivePoints(mask | b, length)) >= 2) points |= b;
  }
  return points;
}

function fourPoints(mask, length) {
  let points = 0;
  const before = fivePoints(mask, length);
  for (let rest = near(mask, length); rest; rest &= rest - 1) {
    const b = rest & -rest;
    if (fivePoints(mask | b, length) & ~before & ~b) points |= b;
  }
  return points;
}

function classifySegmentRaw(length, mask) {
  if (length < 5 || mask === 0) return NONE;
  if (hasFive(mask)) return FIVE;
  let n = popcount(fivePoints(mask, length));
  if (n >= 2) return OPEN_FOUR;
  if (n === 1) return FOUR;
  n = popcount(openFourPoints(mask, length));
  if (n >= 2) return OPEN_THREE;
  if (n === 1) return THREE;
  let best = 0;
  for (let s = 0; s < length - 4; s++) best = Math.max(best, popcount((mask >> s) & 31));
  if (best === 3) return CLOSED_THREE;
  for (let rest = near(mask, length); rest; rest &= rest - 1) {
    if (openFourPoints(mask | (rest & -rest), length)) return TWO;
  }
  if (best === 2) return CLOSED_TWO;
  return ONE;
}

const segmentTables = [];
for (let len = 0; len <= SIZE; len++) segmentTables.push(new Int8Array(1 << len).fill(-1));

export function classifySegment(length, mask) {
  const table = segmentTables[length];
  let s = table[mask];
  if (s < 0) s = table[mask] = classifySegmentRaw(length, mask);
  return s;
}

export const POW3 = [];
for (let k = 0, p = 1; k < 16; k++, p *= 3) POW3.push(p);

// ordering value of each shape, indexed by shape id
const ORDER_VALUE = [0, 1, 4, 12, 20, 60, 90, 250, 2000, 10000];

// per line key: shapes, win points, four points and the move ordering
// summary (value, number of threes) for each color, all indexed by color
const lineCache = new Map();

export function lineInfo(key, length) {
  const ck = key * 16 + length;
  let info = lineCache.get(ck);
  if (info === undefined) {
    info = computeLineInfo(key, length);
    lineCache.set(ck, info);
  }
  return info;
}

// what a stone at each position of the line would do, per color c:
//   gain[c][pos]    ordering value gained by c
//   blocks[c][pos]  opponent threes broken
//   four[c][pos]    1 if c gets a five point on this line
function moveTable(info) {
  if (info.table) return info.table;
  const { key, length } = info;
  const t = { gain: [null, new Int32Array(length), new Int32Array(length)],
    blocks: [null, new Int8Array(length), new Int8Array(length)],
    four: [null, new Int8Array(length), new Int8Array(length)] };
  let rest = key;
  for (let pos = 0; pos < length; pos++, rest = Math.floor(rest / 3)) {
    if (rest % 3) continue;
    for (let c = 1; c <= 2; c++) {
      const after = lineInfo(key + c * POW3[pos], length);
      t.gain[c][pos] = after.value[c] - info.value[c];
      t.blocks[c][pos] = info.threes[3 - c] - after.threes[3 - c];
      t.four[c][pos] = after.wins[c] ? 1 : 0;
    }
  }
  return (info.table = t);
}

function computeLineInfo(key, length) {
  const cells = [];
  for (let k = 0, rest = key; k < length; k++) { cells.push(rest % 3); rest = Math.floor(rest / 3); }
  const info = { key, length, table: null, shapes: [null, [], []], wins: [0, 0, 0], fours: [0, 0, 0],
    value: [0, 0, 0], threes: [0, 0, 0] };
  for (let color = 1; color <= 2; color++) {
    let start = 0, mask = 0;
    for (let k = 0; k <= length; k++) {
      if (k === length || cells[k] === 3 - color) {
        const segLen = k - start;
        const shape = classifySegment(segLen, mask);
        if (shape !== NONE) {
          info.shapes[color].push(shape);
          info.value[color] += ORDER_VALUE[shape];
          if (shape === THREE || shape === OPEN_THREE) info.threes[color]++;
          if (shape === FOUR || shape === OPEN_FOUR) info.wins[color] |= fivePoints(mask, segLen) << start;
          if (shape >= CLOSED_THREE && shape <= OPEN_FOUR) info.fours[color] |= fourPoints(mask, segLen) << start;
        }
        start = k + 1;
        mask = 0;
      } else if (cells[k] === color) {
        mask |= 1 << (k - start);
      }
    }
  }
  return info;
}

// ---- board ----

const DIRECTIONS = [[0, 1], [1, 0], [1, 1], [1, -1]];
const CANDIDATE_RADIUS = 2;
const inBounds = (i, j) => i >= 0 && i < SIZE && j >= 0 && j < SIZE;

export const LINE_CELLS = [];
for (const [di, dj] of DIRECTIONS) {
  for (let i = 0; i < SIZE; i++) {
    for (let j = 0; j < SIZE; j++) {
      if (inBounds(i - di, j - dj)) continue;
      const cells = [];
      for (let x = i, y = j; inBounds(x, y); x += di, y += dj) cells.push(x * SIZE + y);
      if (cells.length >= 5) LINE_CELLS.push(cells);
    }
  }
}
const LINE_LEN = LINE_CELLS.map(c => c.length);
const NLINES = LINE_CELLS.length;

// for each cell, flat triples of (line id, position in line, 3 ** position)
const CELL_LINES = Array.from({ length: SIZE * SIZE }, () => []);
LINE_CELLS.forEach((cells, lid) => cells.forEach((idx, pos) => CELL_LINES[idx].push(lid, pos, POW3[pos])));

const NEIGHBORS = [];
for (let idx = 0; idx < SIZE * SIZE; idx++) {
  const i = Math.floor(idx / SIZE), j = idx % SIZE, list = [];
  for (let x = i - CANDIDATE_RADIUS; x <= i + CANDIDATE_RADIUS; x++) {
    for (let y = j - CANDIDATE_RADIUS; y <= j + CANDIDATE_RADIUS; y++) {
      if (inBounds(x, y) && (x !== i || y !== j)) list.push(x * SIZE + y);
    }
  }
  NEIGHBORS.push(list);
}

// zobrist keys as two 32 bit halves; the combined key keeps 53 bits
function mulberry32(seed) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return (t ^ (t >>> 14)) >>> 0;
  };
}
const rand = mulberry32(20250818);
const ZOB_HI = [null, new Uint32Array(SIZE * SIZE), new Uint32Array(SIZE * SIZE)];
const ZOB_LO = [null, new Uint32Array(SIZE * SIZE), new Uint32Array(SIZE * SIZE)];
for (let c = 1; c <= 2; c++) {
  for (let k = 0; k < SIZE * SIZE; k++) { ZOB_HI[c][k] = rand(); ZOB_LO[c][k] = rand(); }
}
const ZOB_SIDE_HI = rand(), ZOB_SIDE_LO = rand();

export const CENTER = Math.floor(SIZE / 2) * SIZE + Math.floor(SIZE / 2);

export class Board {
  constructor() {
    this.cells = new Int8Array(SIZE * SIZE);
    this.moves = [];
    this.lineKeys = new Int32Array(NLINES);
    this.lineInfos = LINE_LEN.map(n => lineInfo(0, n));
    this.counts = [null, new Int32Array(NSHAPES), new Int32Array(NSHAPES)];
    this.near = new Int16Array(SIZE * SIZE);
    this.hashHi = 0;
    this.hashLo = 0;
  }

  get side() { return this.moves.length % 2 === 0 ? BLACK : WHITE; }
  get hash() { return (this.hashHi & 0x1FFFFF) * 4294967296 + this.hashLo; }

  play(idx) {
    const color = this.side;
    this.updateLines(idx, color);
    this.cells[idx] = color;
    this.hashHi = (this.hashHi ^ ZOB_HI[color][idx] ^ ZOB_SIDE_HI) >>> 0;
    this.hashLo = (this.hashLo ^ ZOB_LO[color][idx] ^ ZOB_SIDE_LO) >>> 0;
    for (const n of NEIGHBORS[idx]) this.near[n]++;
    this.moves.push(idx);
  }

  unplay() {
    const idx = this.moves.pop();
    const color = this.cells[idx];
    this.updateLines(idx, -color);
    this.cells[idx] = EMPTY;
    this.hashHi = (this.hashHi ^ ZOB_HI[color][idx] ^ ZOB_SIDE_HI) >>> 0;
    this.hashLo = (this.hashLo ^ ZOB_LO[color][idx] ^ ZOB_SIDE_LO) >>> 0;
    for (const n of NEIGHBORS[idx]) this.near[n]--;
  }

  updateLines(idx, delta) {
    const keys = this.lineKeys, infos = this.lineInfos;
    const black = this.counts[1], white = this.counts[2];
    const lines = CELL_LINES[idx];
    for (let k = 0; k < lines.length; k += 3) {
      const lid = lines[k];
      const key = keys[lid] += delta * lines[k + 2];
      const before = infos[lid].shapes;
      const after = (infos[lid] = lineInfo(key, LINE_LEN[lid])).shapes;
      for (const s of before[1]) black[s]--;
      for (const s of before[2]) white[s]--;
      for (const s of after[1]) black[s]++;
      for (const s of after[2]) white[s]++;
    }
  }

  // the player who just moved made five
  lastMoveWon() { return this.counts[3 - this.side][FIVE] > 0; }

  isFull() { return this.moves.length === SIZE * SIZE; }

  // cells of the five made by the last move, for display
  winningLine() {
    if (!this.moves.length) return null;
    const idx = this.moves[this.moves.length - 1], color = this.cells[idx];
    const i = Math.floor(idx / SIZE), j = idx % SIZE;
    for (const [di, dj] of DIRECTIONS) {
      const run = [idx];
      for (const sign of [1, -1]) {
        for (let x = i + sign * di, y = j + sign * dj; inBounds(x, y) && this.cells[x * SIZE + y] === color;
          x += sign * di, y += sign * dj) run.push(x * SIZE + y);
      }
      if (run.length >= 5) return run.sort((a, b) => a - b);
    }
    return null;
  }

  hasFour(color) {
    const c = this.counts[color];
    return c[FOUR] + c[OPEN_FOUR] > 0;
  }

  winCells(color) {
    if (!this.hasFour(color)) return [];
    return this.linePoints(color, "wins");
  }

  fourCells(color) {
    const c = this.counts[color];
    if (!(c[CLOSED_THREE] + c[THREE] + c[OPEN_THREE] + c[FOUR] + c[OPEN_FOUR])) return [];
    return this.linePoints(color, "fours");
  }

  linePoints(color, which) {
    const found = new Set();
    const infos = this.lineInfos;
    for (let lid = 0; lid < NLINES; lid++) {
      let points = infos[lid][which][color];
      if (!points) continue;
      const cells = LINE_CELLS[lid];
      for (let pos = 0; points; pos++, points >>= 1) if (points & 1) found.add(cells[pos]);
    }
    return [...found].sort((a, b) => a - b);
  }

  candidates() {
    if (!this.moves.length) return [CENTER];
    const out = [];
    for (let idx = 0; idx < SIZE * SIZE; idx++) if (this.near[idx] && !this.cells[idx]) out.push(idx);
    return out;
  }
}

// ---- evaluation ----

const SCORED_SHAPES = [ONE, CLOSED_TWO, TWO, CLOSED_THREE, THREE, OPEN_THREE];

export const DEFAULT_WEIGHTS = [
  10, 50, 100, 150, 800, 1000,
  12, 58, 115, 172, 920, 1150,
  5000, 20000,
];

export function evaluate(board, weights = DEFAULT_WEIGHTS) {
  const me = board.side;
  const own = board.counts[me], opp = board.counts[3 - me];
  let score = 0;
  for (let k = 0; k < 6; k++) {
    const s = SCORED_SHAPES[k];
    score += weights[k] * own[s] - weights[k + 6] * opp[s];
  }
  if (own[THREE] + own[OPEN_THREE]) score += weights[12];
  if (opp[THREE] + opp[OPEN_THREE] >= 2) score -= weights[13];
  return score;
}

// ---- search ----

export const MATE = 1000000000;
const MATE_BOUND = MATE - 10000;
export const VCF_WIN = MATE - 5000;
const INF = MATE + 1;
const EXACT = 0, LOWER = 1, UPPER = 2;
const TIMEOUT = { timeout: true };

const mateToTT = (score, ply) => score > MATE_BOUND ? score + ply : score < -MATE_BOUND ? score - ply : score;
const mateFromTT = (score, ply) => score > MATE_BOUND ? score - ply : score < -MATE_BOUND ? score + ply : score;
const byScore = (a, b) => b[0] - a[0] || a[1] - b[1];

const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());

export class Engine {
  constructor({ weights = DEFAULT_WEIGHTS, maxDepth = 64, timeLimit = 2.0, beam = 12, vcfDepth = 10, leafVcf = true } = {}) {
    this.weights = weights;
    this.maxDepth = maxDepth;
    this.timeLimit = timeLimit;
    this.beam = beam;
    this.vcfDepth = vcfDepth;
    this.leafVcf = leafVcf;
    this.tt = new Map();
    this.vcfFail = new Map();
  }

  bestMove(board, timeLimit = this.timeLimit, maxDepth = this.maxDepth) {
    return this.iterativeDeepening(board, timeLimit, maxDepth);
  }

  iterativeDeepening(board, timeBudget, maxDepth) {
    this.board = board;
    this.nodes = 0;
    this.start = now();
    this.deadline = this.start + timeBudget * 1000;
    this.info = { depth: 0, score: 0, nodes: 0 };
    this.rootLen = board.moves.length;
    if (this.tt.size > 2000000) this.tt.clear();
    if (this.vcfFail.size > 500000) this.vcfFail.clear();

    const me = board.side, op = 3 - me;
    const mine = board.winCells(me);
    if (mine.length) { this.info.score = MATE - 1; return mine[0]; }
    const theirs = board.winCells(op);
    if (theirs.length) return theirs[0];
    let moves = this.orderMoves(null, true);
    let best = moves[0];
    if (moves.length === 1) return best;
    try {
      const win = this.vcfSearch(this.vcfDepth * 2);
      if (win !== null) { this.info.score = VCF_WIN; return win; }
      for (let depth = 1; depth <= maxDepth; depth++) {
        let bestScore = -INF, alpha = -INF;
        const scored = [];
        for (let k = 0; k < moves.length; k++) {
          const m = moves[k];
          board.play(m);
          let score;
          if (k === 0) {
            score = -this.search(depth - 1, -INF, -alpha, 1);
          } else {
            score = -this.search(depth - 1, -alpha - 1, -alpha, 1);
            if (score > alpha) score = -this.search(depth - 1, -INF, -alpha, 1);
          }
          board.unplay();
          scored.push([score, k, m]);
          if (score > bestScore) {
            bestScore = score;
            alpha = Math.max(alpha, score);
            best = m;
          }
        }
        scored.sort(byScore);
        moves = scored.map(t => t[2]);
        this.info.depth = depth;
        this.info.score = bestScore;
        if (Math.abs(bestScore) > MATE_BOUND) break;
        if (now() - this.start > timeBudget * 400) break;
      }
    } catch (e) {
      if (e !== TIMEOUT) throw e;
      while (board.moves.length > this.rootLen) board.unplay();
    }
    this.info.nodes = this.nodes;
    return best;
  }

  search(depth, alpha, beta, ply) {
    const board = this.board;
    if ((++this.nodes & 1023) === 0 && now() > this.deadline) throw TIMEOUT;
    const me = board.side, op = 3 - me;
    if (board.hasFour(me)) return MATE - ply;
    const threats = board.winCells(op);
    if (threats.length >= 2) return -(MATE - ply - 1);

    const alpha0 = alpha;
    const hash = board.hash;
    const entry = this.tt.get(hash);
    let ttMove = null;
    if (entry !== undefined) {
      ttMove = entry.move;
      if (entry.depth >= depth) {
        const s = mateFromTT(entry.score, ply);
        if (entry.flag === EXACT) return s;
        if (entry.flag === LOWER && s >= beta) return s;
        if (entry.flag === UPPER && s <= alpha) return s;
      }
    }

    let moves, childDepth;
    if (threats.length) {
      moves = threats;
      childDepth = depth;
    } else if (depth <= 0) {
      if (this.leafVcf && this.hasFourMoves(me) && this.vcfSearch(this.vcfDepth) !== null) return VCF_WIN - ply;
      return evaluate(board, this.weights);
    } else {
      moves = this.orderMoves(ttMove, false);
      childDepth = depth - 1;
    }

    let bestScore = -INF, bestMove = moves[0];
    for (let k = 0; k < moves.length; k++) {
      const m = moves[k];
      board.play(m);
      let score;
      if (k === 0) {
        score = -this.search(childDepth, -beta, -alpha, ply + 1);
      } else {
        score = -this.search(childDepth, -alpha - 1, -alpha, ply + 1);
        if (alpha < score && score < beta) score = -this.search(childDepth, -beta, -alpha, ply + 1);
      }
      board.unplay();
      if (score > bestScore) {
        bestScore = score;
        bestMove = m;
        if (score > alpha) {
          alpha = score;
          if (alpha >= beta) break;
        }
      }
    }
    const flag = bestScore <= alpha0 ? UPPER : bestScore >= beta ? LOWER : EXACT;
    this.tt.set(hash, { depth, flag, score: mateToTT(bestScore, ply), move: bestMove });
    return bestScore;
  }

  orderMoves(ttMove, root) {
    const board = this.board;
    const me = board.side, op = 3 - me;
    const infos = board.lineInfos;
    const opThrees = board.counts[op][THREE] + board.counts[op][OPEN_THREE];
    // sort keys pack (gain, idx) so a plain numeric sort gives gain
    // descending, then idx ascending
    let keys = [];
    const rest = [];
    for (const idx of board.candidates()) {
      let gain = 0, blocked = 0, makesFour = 0;
      const lines = CELL_LINES[idx];
      for (let k = 0; k < lines.length; k += 3) {
        const t = moveTable(infos[lines[k]]), pos = lines[k + 1];
        gain += t.gain[me][pos] + t.gain[op][pos];
        blocked += t.blocks[me][pos];
        makesFour |= t.four[me][pos];
      }
      if (opThrees && !blocked && !makesFour) rest.push(gain * 256 + 255 - idx);
      else keys.push(gain * 256 + 255 - idx);
    }
    if (!keys.length) keys = rest;
    keys.sort((a, b) => b - a);
    const n = root ? keys.length : Math.min(keys.length, this.beam);
    const moves = [];
    for (let k = 0; k < n; k++) moves.push(255 - (((keys[k] % 256) + 256) % 256));
    if (ttMove !== null) {
      const at = moves.indexOf(ttMove);
      if (at >= 0) { moves.splice(at, 1); moves.unshift(ttMove); }
    }
    return moves;
  }

  hasFourMoves(color) {
    const c = this.board.counts[color];
    return c[CLOSED_THREE] + c[THREE] + c[OPEN_THREE] > 0;
  }

  fourMoves(color) {
    const board = this.board;
    const found = [];
    for (const idx of board.fourCells(color)) {
      let gain = 0;
      const lines = CELL_LINES[idx];
      for (let k = 0; k < lines.length; k += 3) gain += moveTable(board.lineInfos[lines[k]]).gain[color][lines[k + 1]];
      found.push(gain * 256 + 255 - idx);
    }
    found.sort((a, b) => b - a);
    return found.map(key => 255 - (((key % 256) + 256) % 256));
  }

  vcfSearch(depth) {
    const board = this.board;
    const me = board.side, op = 3 - me;
    const mine = board.winCells(me);
    if (mine.length) return mine[0];
    if (depth <= 0) return null;
    const threats = board.winCells(op);
    if (threats.length >= 2) return null;
    const hash = board.hash;
    const known = this.vcfFail.get(hash);
    if (known !== undefined && known >= depth) return null;
    let moves = this.fourMoves(me);
    if (threats.length) moves = threats.filter(m => moves.includes(m));
    for (const m of moves) {
      if ((++this.nodes & 1023) === 0 && now() > this.deadline) throw TIMEOUT;
      board.play(m);
      const wins = board.winCells(me);
      if (wins.length >= 2) { board.unplay(); return m; }
      board.play(wins[0]);
      const found = this.vcfSearch(depth - 1) !== null;
      board.unplay();
      board.unplay();
      if (found) return m;
    }
    this.vcfFail.set(hash, depth);
    return null;
  }
}

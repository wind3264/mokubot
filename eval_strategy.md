# Gomoku Heuristic Evaluation Strategy — `eval.py`

*Reconstructed reference doc for mokubot_v1. Note: this is not a verbatim transcript of an earlier chat — I couldn't retrieve one — this is the standard implementation of the line-slicing + local-reeval approach your `plan.txt` and `eval.py` comments already point toward, filled out into something buildable.*

## 1. Core idea: slices, not the whole board

Never scan the full 15x15 grid to find patterns. Instead, for any cell you care about, pull out **four 1-D slices** through it — the four directions a 5-in-a-row can run:

```
directions = [(1, 0), (0, 1), (1, 1), (1, -1)]   # horizontal, vertical, diag \, diag /
```

For each direction, extract a short window centered on the cell — radius 4 is enough (length 9), since no pattern relevant to five-in-a-row extends further than 4 cells from a given stone. Off-board cells should be treated as a third symbol (`#` or `-1`), not empty — the edge blocks extension just like an opponent stone does.

```python
def get_line(board, cell, direction, radius=4):
    i, j = cell
    di, dj = direction
    cells = []
    for k in range(-radius, radius + 1):
        ni, nj = i + k * di, j + k * dj
        if 0 <= ni < 15 and 0 <= nj < 15:
            cells.append(board[ni][nj])
        else:
            cells.append(-1)  # off-board sentinel, acts like a blocker
    return cells
```

This turns pattern detection from an O(board size) scan into O(1) work per move (4 fixed-length windows).

## 2. Local re-evaluation: don't rescore the whole board every move

Maintain a running `eval_score` on the `Board` object. On `make_move`:

1. **Before** placing the stone, compute the pattern score contributed by the 4 lines through that cell (for both colors — a move can simultaneously break an opponent pattern and build your own).
2. Place the stone.
3. **After** placing, recompute the pattern score for those same 4 lines.
4. `eval_score += (after - before)`.

`undo_move()` reverses the same delta (recompute before/after in the opposite order, or just cache the delta on the move-history stack so undo is a straight subtraction — cheaper).

This is exactly the "incremental eval delta" your `plan.txt` mentions alongside Zobrist hashing, and it mirrors `check_win` only scanning the 4 lines through the last move for the same reason: **a move can only change patterns on lines passing through it.**

For performance later (this matters a lot once you're running thousands of self-play games for GA tuning), the standard next step is to encode each line as a base-3 or bitmask number and use a precomputed lookup table (window value → score) instead of re-parsing strings every call. Don't build this yet — get the naive string/tuple version correct and tested first, then swap the internals once `perft`-style tests pass.

## 3. Pattern taxonomy and priority

Patterns are ranked by "how many tempo-forcing moves until a win," which is the same ranking VCF/VCT search uses — your heuristic is essentially a cheap, non-recursive approximation of that search.

| Rank | Pattern | Example (`X`=you, `O`=opp, `.`=empty) | Why it matters |
|---|---|---|---|
| 1 | Five in a row | `XXXXX` | Game over |
| 2 | Open four | `.XXXX.` | Two ways to complete five — unblockable, forced win next move |
| 3 | Simple/closed four | `OXXXX.` or `XX.XX` | One way to complete five — opponent *must* block or lose |
| 4 | Double three (fork) | two independent open threes from one stone | Opponent can only block one → becomes an open four either way |
| 5 | Open three | `.XXX.` | If unanswered, becomes an open four next move |
| 6 | Broken/gapped three | `X.XX.` or `XX.X.` | Same forcing power as open three, less visually obvious — don't undercount these |
| 7 | Blocked three | `OXXX.` (one end dead) | Weak — can only become a simple four, not an open one |
| 8 | Open two | `.XX.` | Developmental, worth tracking for move ordering |
| 9 | Split two | `X.X` | Weak developmental shape |
| 10 | Single stone / potential | isolated `X` with open space around | Tiebreaker / opening-book-ish signal |

Note on rows 4 and 6: a **double three** and a **broken three** are different things — don't confuse them. Double three = one move creates two separate open-three lines (a fork). Broken three = a single line with a gap in it (`X.XX`) that's one move from becoming an open four, same threat level as a plain open three.

## 4. Recommended starting weights

These are reasonable defaults to seed your genetic algorithm with — GA tuning will drift them, but starting near sane values gets you converging faster than starting from zero/random.

| Pattern | Own-stone score | Notes |
|---|---|---|
| Five | `WIN` (e.g. `10**8`, or just short-circuit and return immediately — don't let this get summed with anything) | terminal, handle as a special case in `evaluate`, not just a big number |
| Open four | `100,000` | treat as equivalent to a forced win |
| Simple four | `10,000` | |
| Double three (fork) | `50,000` | this should NOT just be `2 × open_three_score` — apply an explicit fork bonus, otherwise your heuristic won't recognize a fork as being nearly as strong as a four |
| Open three | `1,000` | |
| Broken three | `800` | slightly under open three — one square less flexible |
| Blocked three | `150` | |
| Open two | `100` | |
| Split two | `80` | |
| Simple two (one open end) | `50` | |
| Single stone potential | `10` | small positional nudge |

**Defensive weighting:** apply a multiplier of roughly `1.1`–`1.2` to *opponent* pattern scores relative to your own when combining into a single eval number (i.e., `eval = my_score - defense_mult * opp_score`). Renju/Gomoku losses are asymmetric — failing to block a live four loses immediately, while failing to extend your own four just delays a win — so the heuristic should be biased slightly toward not losing. Some implementations skip this and instead handle forced blocks entirely in move ordering / VCF search; either is defensible, but pick one and don't do both or you'll double-count the bias.

**Positional bonus (optional, small):** a small bonus for proximity to center, something like `bonus = max(0, 7 - chebyshev_distance_from_center)` scaled by `~2`, helps opening play look less random before enough stones are on the board for pattern scores to dominate. Keep this weight small — it should matter almost not at all once real patterns exist.

## 5. Fork/double-threat detection

After scoring the 4 individual lines through a cell, check whether ≥2 of them independently qualify as "open three or better." If so, apply the fork bonus (row 4 above) *in addition to or instead of* summing the individual three-scores — a raw sum under-values how strong a fork actually is (opponent literally cannot block both). This lightweight check is the cheap approximation of what full VCT search does properly; you can leave the exhaustive version to `vct_search()` per your `plan.txt` and use this as a fast heuristic-level proxy.

## 6. Wiring this into what you've already got

- `eval.py`'s `detect_five` stub and the comment block listing win/four/three priorities matches rows 1–3 above — that's the right instinct, just needs the windowed-slice implementation instead of a raw board scan.
- `game.py`'s `check_win` should scan the same 4 lines through `last_move` that `evaluate` uses — you can literally share the `get_line` helper between them.
- `minimax.py` currently calls `board.check_win()` with no argument (line 5) but `check_win` is defined taking `last_move` in `game.py` — worth fixing before you go further, since minimax needs to pass `board.moves[-1]`.
- Build order per your own `plan.txt`: get `get_line` + pattern matching solid and unit-tested on hand-built positions *before* wiring in incremental delta tracking — verify the naive "rescan 4 lines from scratch every time" version is correct first, then optimize into true incremental deltas once you trust the pattern matcher.

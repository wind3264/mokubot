# mokubot

A gomoku engine: pattern-based evaluation, alpha-beta search and threat-space search, with evaluation weights tuned by a genetic algorithm.
Play it at https://wind3264.github.io/mokubot/.

Rules are freestyle gomoku on a 15x15 board.
Black moves first, five or more in a row wins (overlines count), and there are no opening restrictions.

## Layout

The Python code is the reference engine, used for testing and tuning.
`web/` holds a JavaScript port of it that runs in the browser.

- `patterns.py` - classifies each line of the board into shapes (open four, four, open three, three, closed three, two, ...).
  A shape is defined by what one more stone could do, so the classification is exact rather than a list of hand-written patterns.
- `game.py` - board state and rules; keeps line keys, shape counts, candidate moves and the Zobrist hash up to date incrementally on every move.
- `eval.py` - static evaluation as weighted shape counts, with separate weights for the side to move and its opponent.
- `minimax.py` - negamax alpha-beta (PVS) with iterative deepening, a transposition table, threat-aware move generation and VCF (victory by continuous fours) search at the root and at leaves.
- `play.py` - human vs engine on the command line, engine vs engine games and self-play batches.
- `tune.py` - genetic algorithm over the evaluation weights.
- `web/` - the website: `engine.js` is the port, `worker.js` runs it off the main thread and `app.js` is the UI.

## Running

```
python play.py                 # play black against the engine in the terminal
python play.py --white         # play white
python play.py --selfplay 20   # engine vs engine
python tune.py                 # tune evaluation weights, writes tuned_weights.json
python -m pytest               # python tests
cd web && npm test             # javascript tests, including parity with the python engine
```

To try the website locally, serve `web/` over http (for example `python -m http.server -d web`) and open it in a browser.

The JavaScript engine is checked against the Python one on fixed positions: shape counts, evaluation, move ordering, VCF results and full searches (down to node counts) must match exactly.
After changing the Python engine, regenerate the fixtures with `python tests/export_fixtures.py` and port the change until `npm test` passes again.

See `plan.txt` for the original plan and `eval_strategy.md` for the evaluation design notes.

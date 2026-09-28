# game-running drivers: engine vs engine, human vs engine, self-play batches
import argparse
import json
import random
import time

from game import SIZE, Board
from minimax import Engine

COLUMNS = "abcdefghijklmno"


def format_move(cell):
    i, j = cell
    return f"{COLUMNS[j]}{SIZE - i}"


def parse_move(text):
    # "h8" style, matching print_board's labels
    text = text.strip().lower()
    if len(text) < 2 or text[0] not in COLUMNS or not text[1:].isdigit():
        raise ValueError(f"cannot read move {text!r}")
    return SIZE - int(text[1:]), COLUMNS.index(text[0])


def engine_player(engine, time_limit=None, max_depth=None):
    return lambda board: engine.best_move(board, time_limit=time_limit, max_depth=max_depth)


def get_human_move(board):
    while True:
        try:
            cell = parse_move(input(f"{'black' if board.black_to_move else 'white'} to move: "))
        except ValueError as err:
            print(err)
            continue
        if board.is_legal_move(cell):
            return cell
        print("that cell is taken or off the board")


def human_player(board):
    board.print_board()
    return get_human_move(board)


def random_opening(rng, n_moves, radius=3):
    """n_moves distinct cells near the center to start a game from."""
    c = SIZE // 2
    cells = [(i, j) for i in range(c - radius, c + radius + 1) for j in range(c - radius, c + radius + 1)]
    return rng.sample(cells, n_moves)


def play_game(player1, player2, opening=(), verbose=False):
    """player1 is black. Returns (result, moves)."""
    board = Board()
    for cell in opening:
        board.make_move(cell)
    players = (player1, player2)
    while not board.is_game_over():
        cell = players[0 if board.black_to_move else 1](board)
        board.make_move(cell)
        if verbose:
            print(len(board.moves), format_move(cell))
    return board.get_result(), list(board.moves)


def save_game_log(path, moves, result, **extra):
    # one json object per line; the dataset for any later weight fitting
    with open(path, "a") as f:
        f.write(json.dumps({"moves": [format_move(m) for m in moves], "result": result, **extra}) + "\n")


def run_self_play_batch(n_games, engine_a, engine_b, max_depth=None, time_limit=None,
                        opening_moves=3, seed=0, log_path=None):
    """Plays n_games (rounded up to pairs) from random openings; each opening
    is played twice with colors swapped. Returns (a wins, b wins, draws)."""
    rng = random.Random(seed)
    a_wins = b_wins = draws = 0
    for _ in range((n_games + 1) // 2):
        opening = random_opening(rng, opening_moves)
        for a_is_black in (True, False):
            pa = engine_player(engine_a, time_limit, max_depth)
            pb = engine_player(engine_b, time_limit, max_depth)
            result, moves = play_game(pa, pb, opening) if a_is_black else play_game(pb, pa, opening)
            if log_path:
                save_game_log(log_path, moves, result, a_is_black=a_is_black)
            if result == "draw":
                draws += 1
            elif (result == "black wins") == a_is_black:
                a_wins += 1
            else:
                b_wins += 1
    return a_wins, b_wins, draws


def main():
    parser = argparse.ArgumentParser(description="play gomoku against mokubot")
    parser.add_argument("--white", action="store_true", help="play white (engine moves first)")
    parser.add_argument("--time", type=float, default=2.0, help="engine seconds per move")
    parser.add_argument("--selfplay", type=int, metavar="N", help="run N engine vs engine games instead")
    parser.add_argument("--depth", type=int, help="fixed search depth for self-play")
    parser.add_argument("--log", help="append finished games to this jsonl file")
    args = parser.parse_args()

    if args.selfplay:
        start = time.time()
        a, b, d = run_self_play_batch(args.selfplay, Engine(), Engine(), max_depth=args.depth,
                                      time_limit=args.time, log_path=args.log)
        print(f"a {a}  b {b}  draws {d}  ({time.time() - start:.0f}s)")
        return

    engine = engine_player(Engine(), time_limit=args.time)
    black, white = (engine, human_player) if args.white else (human_player, engine)
    result, moves = play_game(black, white, verbose=True)
    board = Board()
    for m in moves:
        board.make_move(m)
    board.print_board()
    print(result)
    if args.log:
        save_game_log(args.log, moves, result)


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()

from game import SIZE, Board


def position(black, white, black_to_move=True):
    """Board with the given stones; filler stones in the bottom corners keep
    the stone counts alternating so the requested side is to move."""
    black, white = list(black), list(white)
    fillers = [(14, 0), (14, 14), (12, 0), (12, 14), (14, 2), (14, 12), (12, 2), (12, 12)]
    want = 0 if black_to_move else 1  # len(black) - len(white)
    while len(black) - len(white) > want:
        white.append(fillers.pop())
    while len(black) - len(white) < want:
        black.append(fillers.pop())
    b = Board()
    for k in range(len(black) + len(white)):
        i, j = black[k // 2] if k % 2 == 0 else white[k // 2]
        b.play(i * SIZE + j)
    assert b.black_to_move == black_to_move
    return b

import pytest

from patterns import (CLOSED_THREE, CLOSED_TWO, FIVE, FOUR, NONE, ONE,
                      OPEN_FOUR, OPEN_THREE, THREE, TWO, classify_segment,
                      line_info)


def seg(text):
    mask = sum(1 << k for k, ch in enumerate(text) if ch == "X")
    return classify_segment(len(text), mask)


@pytest.mark.parametrize("text,shape", [
    ("XXXXX", FIVE),
    ("XXXXXX", FIVE),
    (".XXXX.", OPEN_FOUR),
    ("X.XXX.X", OPEN_FOUR),
    ("XXXX.", FOUR),
    (".XXXX", FOUR),
    ("XX.XX", FOUR),
    ("X.XXX", FOUR),
    ("..XXX..", OPEN_THREE),
    ("...XXX...", OPEN_THREE),
    (".XXX..", THREE),
    (".X.XX.", THREE),
    (".XX.X.", THREE),
    (".XXX.", CLOSED_THREE),
    ("XXX..", CLOSED_THREE),
    ("X.X.X", CLOSED_THREE),
    ("XX..X", CLOSED_THREE),
    ("..XX..", TWO),
    (".X.X..", TWO),
    ("..X..X..", TWO),
    ("XX...", CLOSED_TWO),
    (".XX..", CLOSED_TWO),
    ("X...X", CLOSED_TWO),
    ("X....", ONE),
    ("..X...", ONE),
    (".....", NONE),
    ("XXXX", NONE),  # too short to ever make five
])
def test_segment_shapes(text, shape):
    assert seg(text) == shape


def line(text):
    key = 0
    for k, ch in enumerate(text):
        key += {".": 0, "X": 1, "O": 2}[ch] * 3 ** k
    return line_info(key, len(text))


def test_opponent_stones_split_segments():
    shapes, wins, _ = line("OXXXX.......OO.")
    assert shapes[1] == (FOUR,)
    assert wins[1] == 1 << 5
    assert wins[2] == 0


def test_line_with_several_shapes():
    shapes, _, _ = line("..XX...O..OOO..")
    assert shapes[1] == (TWO,)
    assert shapes[2] == (OPEN_THREE,)


def test_open_four_has_two_win_points():
    shapes, wins, _ = line("....OOOO.......")
    assert shapes[2] == (OPEN_FOUR,)
    assert wins[2] == (1 << 3) | (1 << 8)


def test_four_points():
    _, _, fours = line("..XXX..O.......")
    # any of the four cells around the three makes a four
    assert fours[1] == sum(1 << k for k in (0, 1, 5, 6))
    _, _, fours = line("OXX.X..........")
    assert fours[1] == (1 << 3) | (1 << 5)
    assert fours[2] == 0

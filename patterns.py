# pattern classification for a single line of the board
#
# a line is split into segments at opponent stones and board edges. a segment
# only holds own stones and empty cells, so its shape depends on nothing but
# its length and the bitmask of own stones. shapes are defined by what one
# more stone could do, which is exactly the forcing hierarchy gomoku runs on:
#   five         - five (or more) in a row already
#   open four    - two or more cells complete a five, cannot be blocked
#   four         - exactly one cell completes a five, must be blocked
#   open three   - two or more cells make an open four (e.g. ..XXX..)
#   three        - exactly one cell makes an open four (e.g. .X.XX. or |.XXX..)
#   closed three - some cell makes a four, none make an open four
#   two          - some cell makes a three
#   closed two   - two more stones could make a four
#   one          - any own stone with room for five
NONE, ONE, CLOSED_TWO, TWO, CLOSED_THREE, THREE, OPEN_THREE, FOUR, OPEN_FOUR, FIVE = range(10)
NSHAPES = 10
SHAPE_NAMES = ["none", "one", "closed_two", "two", "closed_three", "three",
               "open_three", "four", "open_four", "five"]


def has_five(mask):
    return (mask & (mask >> 1) & (mask >> 2) & (mask >> 3) & (mask >> 4)) != 0


def five_points(mask, length):
    # bitmask of empty cells that would complete five in a row
    points = 0
    for s in range(length - 4):
        w = (mask >> s) & 31
        if w != 31 and bin(w).count("1") == 4:
            points |= (~w & 31) << s
    return points


def _near(mask, length):
    # empty cells within distance 4 of an own stone; nothing further away can
    # take part in a five with the existing stones
    near = mask
    for d in range(1, 5):
        near |= (mask << d) | (mask >> d)
    return near & ~mask & ((1 << length) - 1)


def _bits(mask):
    while mask:
        low = mask & -mask
        yield low
        mask ^= low


def _open_four_points(mask, length):
    # empty cells that turn the segment into an open four
    points = 0
    for b in _bits(_near(mask, length)):
        if bin(five_points(mask | b, length)).count("1") >= 2:
            points |= b
    return points


_segment_cache = {}


def classify_segment(length, mask):
    key = (length << 16) | mask
    shape = _segment_cache.get(key)
    if shape is None:
        shape = _classify_segment(length, mask)
        _segment_cache[key] = shape
    return shape


def _classify_segment(length, mask):
    if length < 5 or mask == 0:
        return NONE
    if has_five(mask):
        return FIVE
    n = bin(five_points(mask, length)).count("1")
    if n >= 2:
        return OPEN_FOUR
    if n == 1:
        return FOUR
    n = bin(_open_four_points(mask, length)).count("1")
    if n >= 2:
        return OPEN_THREE
    if n == 1:
        return THREE
    best = 0
    for s in range(length - 4):
        best = max(best, bin((mask >> s) & 31).count("1"))
    if best == 3:
        return CLOSED_THREE
    for b in _bits(_near(mask, length)):
        if _open_four_points(mask | b, length):
            return TWO
    if best == 2:
        return CLOSED_TWO
    return ONE


# line keys are base 3 numbers, cell k of the line contributing color * 3**k
POW3 = [3 ** k for k in range(16)]

_line_cache = {}


def line_info(key, length):
    """(shapes, win_points, four_points) for black and white on the line.

    shapes[c] is a tuple of segment shapes (NONE omitted) for color c,
    win_points[c] is a bitmask of line positions where color c completes five
    and four_points[c] a bitmask of positions where color c makes a four.
    """
    ck = key * 16 + length
    info = _line_cache.get(ck)
    if info is None:
        info = _line_info(key, length)
        _line_cache[ck] = info
    return info


def _line_info(key, length):
    cells = []
    for _ in range(length):
        cells.append(key % 3)
        key //= 3
    shapes = [(), (), ()]
    wins = [0, 0, 0]
    fours = [0, 0, 0]
    for color in (1, 2):
        found = []
        start = 0
        mask = 0
        for k in range(length + 1):
            if k == length or cells[k] == 3 - color:
                seg_len = k - start
                shape = classify_segment(seg_len, mask)
                if shape != NONE:
                    found.append(shape)
                    if shape == FOUR or shape == OPEN_FOUR:
                        wins[color] |= five_points(mask, seg_len) << start
                    if CLOSED_THREE <= shape <= OPEN_FOUR:
                        fours[color] |= _four_points(mask, seg_len) << start
                start = k + 1
                mask = 0
            elif cells[k] == color:
                mask |= 1 << (k - start)
        shapes[color] = tuple(found)
    return shapes, wins, fours


def _four_points(mask, length):
    # empty cells that give the segment a new five point
    points = 0
    before = five_points(mask, length)
    for b in _bits(_near(mask, length)):
        if five_points(mask | b, length) & ~before & ~b:
            points |= b
    return points

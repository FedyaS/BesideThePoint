import random

def pick_point():
    return random.random(), random.random()

def trial():
    blue_x, blue_y = pick_point()
    red_x, red_y = pick_point()

    dbottom = blue_y
    dtop = 1 - blue_y
    dright = 1 - blue_x
    dleft = blue_x

    closest_side_dist = min(dbottom, dtop, dright, dleft)

    if dbottom == closest_side_dist:
        side_range = ((0, 0), (1, 0))
        constant = ('y', 0)
    elif dtop == closest_side_dist:
        side_range = ((0, 1), (1, 1))
        constant = ('y', 1)
    elif dright == closest_side_dist:
        side_range = ((1, 0), (1, 1))
        constant = ('x', 1)
    else:
        side_range = ((0, 0), (0, 1))
        constant = ('x', 0)

    mid_x = (blue_x + red_x) / 2
    mid_y = (blue_y + red_y) / 2
    slope = (blue_y - red_y) / (blue_x - red_x)
    neg_recip_slope = -1 / slope

    if constant[0] == 'x':
        x = constant[1]
        other_cord = neg_recip_slope * (x - mid_x) + mid_y
        intersection_point = (x, other_cord) if 0 <= other_cord <= 1 else None
    else:
        y = constant[1]
        other_cord = (y - mid_y) / neg_recip_slope + mid_x
        intersection_point = (other_cord, y) if 0 <= other_cord <= 1 else None

    solution = "Solution" if intersection_point else "No Solution"

    return {
        'blue_point': (blue_x, blue_y),
        'red_point': (red_x, red_y),
        'closest_side': side_range,
        'mid_point': (mid_x, mid_y),
        'neg_recip_slope': neg_recip_slope,
        'intersection_point': intersection_point,
        'solution': solution
    }


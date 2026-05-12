def piecewise_scale(value, points):
    """
    Interpolate value between competitive scaling points.

    points example:
    [
        (50, 20),
        (60, 35),
        (70, 50),
        (80, 70),
        (90, 85),
        (100, 100),
    ]
    """

    if value is None:
        return 0

    value = float(value)

    points = sorted(points, key=lambda x: x[0])

    if value <= points[0][0]:
        return points[0][1]

    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]

        if x1 <= value <= x2:
            ratio = (value - x1) / (x2 - x1)
            return round(y1 + ratio * (y2 - y1), 2)

    return points[-1][1]


def normalize_adr(adr):
    return piecewise_scale(
        adr,
        [
            (50, 20),
            (60, 35),
            (70, 50),
            (80, 68),
            (90, 84),
            (100, 95),
            (110, 99),
            (120, 100),
        ],
    )


def normalize_kd(kd):
    return piecewise_scale(
        kd,
        [
            (0.70, 10),
            (0.80, 20),
            (0.90, 35),
            (1.00, 50),
            (1.10, 65),
            (1.20, 80),
            (1.30, 90),
            (1.40, 97),
            (1.50, 100),
        ],
    )


def normalize_hs(hs):
    return piecewise_scale(
        hs,
        [
            (20, 10),
            (30, 30),
            (40, 55),
            (50, 75),
            (60, 90),
            (70, 100),
        ],
    )


def normalize_entry_success(rate):
    return piecewise_scale(
        rate,
        [
            (0.30, 20),
            (0.40, 40),
            (0.50, 60),
            (0.60, 80),
            (0.70, 100),
        ],
    )


def normalize_entry_rate(rate):
    return piecewise_scale(
        rate,
        [
            (0.10, 20),
            (0.15, 40),
            (0.20, 60),
            (0.25, 80),
            (0.30, 100),
        ],
    )
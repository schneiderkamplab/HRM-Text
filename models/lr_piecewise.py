"""Optional absolute-step piecewise-linear base learning rate."""
import math


def validate_lr_points(points):
    if len(points) < 2:
        raise ValueError("lr_piecewise_points requires at least two anchors")
    previous = -1
    for step, rate in points:
        if step < 0 or int(step) != step or step <= previous:
            raise ValueError("LR anchor steps must be nonnegative and strictly increasing")
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("LR anchor rates must be finite and positive")
        previous = step


def piecewise_lr(points, step):
    if step <= points[0][0]:
        return points[0][1]
    for (start, low), (end, high) in zip(points, points[1:]):
        if step <= end:
            return low + (high - low) * ((step - start) / (end - start))
    return points[-1][1]

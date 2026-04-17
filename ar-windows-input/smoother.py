class EMA:
    """Exponential moving average for a single scalar."""
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self._value = None

    def update(self, x: float) -> float:
        if self._value is None:
            self._value = x
        else:
            self._value += self.alpha * (x - self._value)
        return self._value

    def reset(self):
        self._value = None

    @property
    def value(self):
        return self._value


class PositionSmoother:
    """EMA smoother for an (x, y) position."""
    def __init__(self, alpha: float = 0.4):
        self.x = EMA(alpha)
        self.y = EMA(alpha)

    def update(self, x: float, y: float):
        return self.x.update(x), self.y.update(y)

    def reset(self):
        self.x.reset()
        self.y.reset()

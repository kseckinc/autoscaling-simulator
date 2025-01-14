import numbers
import pandas as pd

class PricePerUnitTime:

    def __init__(self, value : float,
                 time_unit : pd.Timedelta = pd.Timedelta(1, unit = 'h')):

        self.value = value
        self.time_unit = time_unit

    def __mul__(self, other):

        if isinstance(other, pd.Timedelta):
            time_ratio = other / self.time_unit
            return self.value * time_ratio

        elif isinstance(other, numbers.Number):
            return self.__class__(self.value, self.time_unit)

        else:
            raise TypeError(f'Unexpected type {other.__class__.__name__}')

    def __rmul__(self, other):

        return self.__mul__(other)

    def __repr__(self):

        return f'{self.__class__.__name__}(value = {self.value}, \
                                           time_unit = {self.time_unit})'

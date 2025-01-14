import operator
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod

class MetricCategory(ABC):

    @classmethod
    @abstractmethod
    def to_metric(cls, config : dict):

        pass

    @classmethod
    @abstractmethod
    def to_target_value(cls, config : dict):

        pass

    @classmethod
    @abstractmethod
    def convert_df(cls, df : pd.DataFrame):

        pass

    @classmethod
    @abstractmethod
    def to_scaling_representation(cls, val : float):

        pass

    @abstractmethod
    def __init__(self):

        pass
        
    @property
    def value(self):

        return self._value

    @property
    def isnan(self):

        return np.isnan(self._value)

    def __add__(self, other):

        return self._add(other, 1)

    def __sub__(self, other):

        return self._add(other, -1)

    def __mul__(self, multiplier : float):

        return self.__class__(self._value * multiplier)

    def __rmul__(self, multiplier : int):

        return self.__mul__(multiplier)

    def __truediv__(self, other):

        return self._div(other, operator.truediv)

    def __floordiv__(self, other):

        return self._div(other, operator.floordiv)

    def __gt__(self, other):

        return self._comp(other, operator.gt)

    def __ge__(self, other):

        return self._comp(other, operator.ge)

    def __lt__(self, other):

        return self._comp(other, operator.lt)

    def __le__(self, other):

        return self._comp(other, operator.le)

    def __eq__(self, other):

        return self._comp(other, operator.eq)

    def __ne__(self, other):

        return self._comp(other, operator.ne)

    def __repr__(self):

        return f'{self.__class__.__name__}({self._value})'

    def _add(self, other, sign : int):

        if not isinstance(other, self.__class__):
            raise TypeError(f'Cannot combine object of type {self.__class__.__name__} with object of type {other.__class__.__name__}')

        return self.__class__(self._value + sign * other._value)

    def _div(self, other, op):

        if not isinstance(other, self.__class__):
            raise ValueError(f'Cannot divide by the value of an unrecognized type {other.__class__.__name__}')

        if other._value == 0:
            raise ValueError('An attempt to divide by zero-size')

        return op(self._value, other._value)

    def _comp(self, other, comparison_op) -> bool:

        """ Implements common comparison logic """

        if not isinstance(other, self.__class__):
            raise TypeError(f'Unexpected type of an operand when comparing with {self.__class__.__name__}: {other.__class__.__name__}')

        return comparison_op(self._value, other._value)

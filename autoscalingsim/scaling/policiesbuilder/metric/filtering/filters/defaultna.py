import pandas as pd

from ..valuesfilter import ValuesFilter

from ......utils.error_check import ErrorChecker

@ValuesFilter.register('defaultNA')
class DefaultNA(ValuesFilter):

    """
    Substitutes all the NA values for the default value, e.g. 0.
    """

    def __init__(self, config : dict):

        self.default_value = ErrorChecker.key_check_and_load('default_value', config, self.__class__.__name__)

    def __call__(self, values : pd.DataFrame):

        return values.fillna(self.default_value)
import pandas as pd

from ..seasonal_load_parser import SeasonalLoadPatternParser
from .......utils.error_check import ErrorChecker

@SeasonalLoadPatternParser.register('values')
class MultipleValuesSeasonalLoadPatternParser(SeasonalLoadPatternParser):

    @staticmethod
    def parse(pattern : dict):

        monthly_vals = {}
        for finer_pattern in ErrorChecker.key_check_and_load('params', pattern):

            month = ErrorChecker.key_check_and_load('month', finer_pattern)
            if not month in SeasonalLoadPatternParser.MONTHS_IDS:
                raise ValueError(f'Unknown month provided: {month}')

            month_id = SeasonalLoadPatternParser.MONTHS_IDS[month]
            if not month_id in monthly_vals:
                monthly_vals[month_id] = {}

            day_of_week = ErrorChecker.key_check_and_load('day_of_week', finer_pattern)
            if day_of_week == 'weekday':
                for day_id in range(5):
                    monthly_vals[month_id][day_id] = ErrorChecker.key_check_and_load('values', finer_pattern)
            elif day_of_week == 'weekend':
                for day_id in range(5, 7):
                    monthly_vals[month_id][day_id] = ErrorChecker.key_check_and_load('values', finer_pattern)
            else:
                raise ValueError(f'day_of_week value {day_of_week} undefined for {self.__class__.__name__}')

        return monthly_vals
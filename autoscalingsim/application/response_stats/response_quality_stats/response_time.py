import pandas as pd

from autoscalingsim.load.request import Request
from .response_quality_stats import ResponseQualityStats
from autoscalingsim.utils.timeline import Timeline

class ResponseTimeStats (ResponseQualityStats):

    def add_request(self, cur_timestamp : pd.Timestamp, req : Request):

        self._add_request_stats(cur_timestamp, req.cumulative_time.microseconds / 1000, [req.request_type])
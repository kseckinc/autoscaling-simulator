import pandas as pd

from ....load.request import Request

class RequestsProcessor:

    """
    Wraps the logic of requests processing for the given region.
    """

    def __init__(self):

        self.in_processing_simultaneous = []
        self.out = {}
        self.stat = {}

    def step(self,
             time_budget : pd.Timedelta):

        if len(self.in_processing_simultaneous) > 0:
            # Find minimal leftover duration, subtract it, and propagate the request
            min_leftover_time = min([req.processing_time_left for req in self.in_processing_simultaneous])
            min_time_to_subtract = min(min_leftover_time, time_budget)
            new_in_processing_simultaneous = []

            for req in self.in_processing_simultaneous:
                new_time_left = req.processing_time_left - min_time_to_subtract
                req.cumulative_time += min_time_to_subtract
                if new_time_left > pd.Timedelta(0, unit = 'ms'):
                    req.processing_time_left = new_time_left
                    new_in_processing_simultaneous.append(req)
                else:
                    req.processing_time_left = pd.Timedelta(0, unit = 'ms')
                    self.stat[req.request_type] = self.stat.get(req.request_type, 0) - 1
                    if not req.processing_service in self.out:
                        self.out[req.processing_service] = []
                    self.out[req.processing_service].append(req)

            self.in_processing_simultaneous = new_in_processing_simultaneous
            time_budget -= min_time_to_subtract

        return time_budget

    def start_processing(self,
                         req : Request):

        self.stat[req.request_type] = self.stat.get(req.request_type, 0) + 1
        self.in_processing_simultaneous.append(req)

    def requests_in_processing(self):

        return len(self.in_processing_simultaneous)

    def get_processed_for_service(self,
                                  service_name : str):

        processed_for_service = []
        if service_name in self.out:
            processed_for_service.extend(self.out[service_name])
            self.out[service_name] = []

        return processed_for_service

    def get_in_processing_stat(self):

        return self.stat
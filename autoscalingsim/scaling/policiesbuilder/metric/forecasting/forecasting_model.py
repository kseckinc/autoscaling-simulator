import pandas as pd

from abc import ABC, abstractmethod

class ForecastingModel(ABC):
    """
    Wraps the forecasting model used by MetricForecaster.
    """

    _Registry = {}

    @abstractmethod
    def __init__(self, forecasting_model_params : dict):

        pass

    @abstractmethod
    def fit(self, data : pd.DataFrame):

        pass

    @abstractmethod
    def predict(self, metric_vals : pd.DataFrame, fhorizon_in_steps : int, resolution : pd.Timedelta):

        pass

    @classmethod
    def register(cls, name : str):

        def decorator(forecasting_model_cls):
            cls._Registry[name] = forecasting_model_cls
            return forecasting_model_cls

        return decorator

    @classmethod
    def get(cls, name : str):

        if not name in cls._Registry:
            raise ValueError(f'An attempt to use the non-existent forecasting model {name}')

        return cls._Registry[name]

from .models import *
import pandas as pd

from autoscalingsim.scaling.policiesbuilder.metric.correlator.correlator import Correlator
from autoscalingsim.scaling.policiesbuilder.metric.correlator.correlators.maximal_information_correlator.maximal_information_correlator import MaximalInformationCorrelator

@Correlator.register('total-information-coefficient')
class TICCorrelator(MaximalInformationCorrelator):

    def _compute_correlation_internal(self):

        return self.estimator.tic(norm = True)
import numbers
import numpy as np

from ..requests_distribution import SlicedRequestsNumDistribution

from ......utils.error_check import ErrorChecker

@SlicedRequestsNumDistribution.register('normal')
class NormalDistribution:

    """ Generates a random request count in the time slice according to the normal distribution """

    def __init__(self, distribution_params : dict):

        self.mu = ErrorChecker.key_check_and_load('mu', distribution_params, 'distribution_name', self.__class__.__name__)
        self.sigma = ErrorChecker.key_check_and_load('sigma', distribution_params, 'distribution_name', self.__class__.__name__)

    def generate(self, num : int = 1):

        return np.random.normal(self.mu, self.sigma, num)

    def set_avg_param(self, avg_param : numbers.Number):

        self.mu = avg_param
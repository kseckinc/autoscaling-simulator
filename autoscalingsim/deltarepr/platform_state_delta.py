import pandas as pd
import numpy as np
import collections
from collections import defaultdict
from copy import deepcopy

from .regional_delta import RegionalDelta

from autoscalingsim.desired_state.state_duration import StateDuration
from autoscalingsim.scaling.scaling_model.scaling_model import ScalingModel

class PlatformStateDelta:

    @classmethod
    def create_enforced_delta(cls, regional_deltas : dict = {}):

        return cls(regional_deltas.copy(), True)

    def __init__(self, regional_deltas : dict = {}, is_enforced : bool = False):

        self.is_enforced = is_enforced
        self.deltas_per_region = dict()
        if isinstance(regional_deltas, list):
            for regional_delta in regional_deltas:
                if not isinstance(regional_delta, RegionalDelta):
                    raise TypeError(f'Expected RegionalDelta on initializing {self.__class__.__name__}, got {regional_delta.__class__.__name__}')

                self.deltas_per_region[regional_delta.region_name] = regional_delta

        elif isinstance(regional_deltas, dict):
            for regional_delta in regional_deltas.values():
                if not isinstance(regional_delta, RegionalDelta):
                    raise TypeError(f'Expected RegionalDelta on initializing {self.__class__.__name__},\
                                    got {regional_delta.__class__.__name__}')

            self.deltas_per_region = deepcopy(regional_deltas)

        else:
            raise TypeError(f'Unknown type of init argument for {self.__class__.__name__}: \
                            {regional_deltas.__class__.__name__}')

    def enforce(self, scaling_model : ScalingModel, delta_timestamp : pd.Timestamp):

        enforced_regional_deltas = defaultdict(list)
        for regional_delta in self.deltas_per_region.values():

            new_timestamped_rd = regional_delta.enforce(scaling_model, delta_timestamp)

            for timestamp, regional_deltas in new_timestamped_rd.items():
                enforced_regional_deltas[timestamp].extend(regional_deltas)

        return { timestamp : self.__class__.create_enforced_delta(reg_deltas_per_ts) \
                    for timestamp, reg_deltas_per_ts in enforced_regional_deltas.items()}

    def till_full_enforcement(self, scaling_model : ScalingModel, delta_timestamp : pd.Timestamp):

        time_till_enforcement_per_reg_delta = { region_name : regional_delta.till_full_enforcement(scaling_model, delta_timestamp) \
                                                    for region_name, regional_delta in self.deltas_per_region.items() }

        return StateDuration(time_till_enforcement_per_reg_delta)

    def __add__(self, other_state_delta : 'PlatformStateDelta'):

        new_regional_deltas = self.deltas_per_region.copy()
        for region_name, regional_delta in other_state_delta:
            if not region_name in new_regional_deltas:
                new_regional_deltas[region_name] = regional_delta
            else:
                new_regional_deltas[region_name] += regional_delta

        return self.__class__(new_regional_deltas)

    @property
    def nodes_change(self):

        result = collections.defaultdict(int)
        for regional_delta in self.deltas_per_region.values():
            for node_type, nodes_count in regional_delta.nodes_change.items():
                result[node_type] += nodes_count

        return result

    @property
    def contains_platform_state_change(self):

        return np.any([regional_delta.contains_platform_state_change for regional_delta in self.deltas_per_region.values()])

    @property
    def contains_platform_scale_up(self):

        return np.any([regional_delta.contains_platform_scale_up for regional_delta in self.deltas_per_region.values()])

    def __iter__(self):

        return PlatformStateDeltaIterator(self)

    def __repr__(self):

        return f'{self.__class__.__name__}( regional_deltas = {self.deltas_per_region}, \
                                            is_enforced = {self.is_enforced})'

class PlatformStateDeltaIterator:

    def __init__(self, state_delta : PlatformStateDelta):

        self._state_delta = state_delta
        self._region_names = list(state_delta.deltas_per_region.keys())
        self._index = 0

    def __next__(self):

        if self._index < len(self._region_names):
            region_name = self._region_names[self._index]
            self._index += 1
            return (region_name, self._state_delta.deltas_per_region[region_name])

        raise StopIteration

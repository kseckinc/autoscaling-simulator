import pandas as pd
import numpy as np

from abc import ABC, abstractmethod

import ....utils.state.aggregators

class ScalingEffectAggregationRule(ABC):

    """
    An aggregation rule for the desired scaling effect values produced
    by the metrics for the associated entity.
    Two different approaches to aggregation are available:

        Sequential: the desired scaling effect is computed on a metric-by-metric
                    basis starting with the metric of the highest priority, then
                    the desired scaling effect computed for the previous metric is
                    used as limits for the next metric to compute. The scaling
                    effect produced by the last metric in the chain is used
                    as the final desired scaling effect.

        Parallel:   the desired scaling effect is computed at once, using the
                    desired scaling effects computed by every metric. For instance,
                    it can be an average of all the desired scaling effects,
                    or the maximum can be taken.

    """

    def __init__(self,
                 metrics_by_priority):

        self.metrics_by_priority = metrics_by_priority

    @abstractmethod
    def __call__(self):
        pass

class SequentialScalingEffectAggregationRule(ScalingEffectAggregationRule):

    """
    Sequentially calls metrics to produce desired scaling effect values for the
    associated entity, each subsequent metric gets the soft limits on the desired
    scaling effect values from the previous one (if it is not the first metric
    in the sequence).
    """

    def __init__(self,
                 metrics_by_priority,
                 expected_deviation_ratio = 0.25):

        super().__init__(metrics_by_priority)

        if expected_deviation_ratio < 0:
            raise ValueError('expected_deviation_ratio cannot be negative')
        self.expected_deviation_ratio = expected_deviation_ratio

    def __call__(self):

        ordered_metrics = list(self.metrics_by_priority.values())
        if len(ordered_metrics) > 1:
            for regionalized_metric, regionalized_metric_next in zip(ordered_metrics[:-1], ordered_metrics[1:]):
                timeline_by_metric = regionalized_metric()
                timeline_df = pd.DataFrame(columns = ['datetime', 'value'])
                timeline_df = timeline_df.set_index('datetime')
                for timestamp, state in timeline_by_metric.items():
                    aspect_value = state.get_value(regionalized_metric.region_name,
                                                   regionalized_metric.scaled_entity_name)
                    df_to_add = pd.DataFrame(data = {'datetime': timestamp, 'value': aspect_value})
                    df_to_add = df_to_add.set_index('datetime')
                    timeline_df = timeline_df.append(df_to_add)

                min_lim = np.floor((1 - self.expected_deviation_ratio) * timeline_df)
                max_lim = np.ceil((1 + self.expected_deviation_ratio) * timeline_df)
                metric_next.update_limits(min_lim, max_lim)

        return ordered_metrics[-1]()

class ParallelScalingEffectAggregationRule(ScalingEffectAggregationRule):

    """
    Calls all the metrics at once and jointly aggregates their results.
    """

    def __init__(self,
                 metrics_by_priority : dict,
                 aggregation_op_name : str): # TODO: propagate

        super().__init__(metrics_by_priority)
        self.aggregation_op = aggregators.Registry.get(aggregation_op_name)

    def __call__(self):

        # 1. Compute all the desired timelines and determine
        # the finest resolution among them.
        finest_td = pd.Timedelta(10, unit = 'ms')
        max_ts = pd.Timestamp(0)
        ordered_metrics = list(self.metrics_by_priority.values())
        timelines_by_metric = {}
        for regionalized_metric in ordered_metrics:
            timelines_by_metric[regionalized_metric.metric_name] = regionalized_metric()
            ts_list = list(timelines_by_metric[regionalized_metric.metric_name].keys())

            cur_min_td = min(np.diff(ts_list))
            if cur_min_td < finest_td:
                finest_td = cur_min_td

            cur_max_ts = max(ts_list)
            if cur_max_ts > max_ts:
                max_ts = cur_max_ts

        # 2. Impute the timelines that have different resolution to the found one
        for metric_name, timeline in timelines_by_metric.items():
            cur_ts = list(timeline.keys())[0] + finest_td
            prev_val = list(timeline.values())[0]
            while cur_ts < max_ts:
                if not cur_ts in timeline:
                    timeline[cur_ts] = prev_val
                else:
                    prev_val = timeline[cur_ts]
                cur_ts += finest_td

        # 3. Simply aggregate the regionalized entity states using
        # the operation provided in the aggregation rule
        timestamped_states = {}
        for metric_name, timeline in timelines_by_metric.items():
            for timestamp, state in timeline.items():
                if not timestamp in timestamped_states:
                    timestamped_states[timestamp] = []
                timestamped_states[timestamp].append(state)

        desired_states = {}
        for timestamp, states_per_ts in timestamped_states.items():
            desired_states[timestamp] = self.aggregation_op.aggregate(states_per_ts)

        return desired_states

class MaxScalingEffectAggregationRule(ParallelScalingEffectAggregationRule):

    """
    maxScale - pairwise aggregation by taking the max value.
    """

    def __init__(self,
                 metrics_by_priority):

        super().__init__(metrics_by_priority,
                         max)

class MinScalingEffectAggregationRule(ParallelScalingEffectAggregationRule):

    """
    minScale - pairwise aggregation by taking the min value.
    """

    def __init__(self,
                 metrics_by_priority):

        super().__init__(metrics_by_priority,
                         min)

class Registry:

    """
    Stores the scaling aggregation rules classes and organizes access to them.
    """

    registry = {
        'seqScale': SequentialScalingEffectAggregationRule,
        'maxScale': MaxScalingEffectAggregationRule,
        'minScale': MinScalingEffectAggregationRule
    }

    @staticmethod
    def get(name):

        if not name in Registry.registry:
            raise ValueError('An attempt to use the non-existent aggregation rule {}'.format(name))

        return Registry.registry[name]
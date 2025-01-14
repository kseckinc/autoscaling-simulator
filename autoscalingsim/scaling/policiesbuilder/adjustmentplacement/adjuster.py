import pandas as pd
from copy import deepcopy
from abc import ABC, abstractmethod

from .desired_adjustment_calculator.desired_calc import DesiredPlatformAdjustmentCalculator
from .desired_adjustment_calculator.scoring.score_calculator import ScoreCalculator
from .desired_adjustment_calculator.scoring.scorer import Scorer

from autoscalingsim.deltarepr.timelines.services_changes_timeline import TimelineOfDesiredServicesChanges
from autoscalingsim.deltarepr.timelines.delta_timeline import DeltaTimeline
from autoscalingsim.scaling.state_reader import StateReader
from autoscalingsim.scaling.scaling_model import ScalingModel
from autoscalingsim.desired_state.platform_state import PlatformState
from autoscalingsim.desired_state.state_duration import StateDuration
from autoscalingsim.desired_state.service_group.group_of_services_reg import GroupOfServicesRegionalized
from autoscalingsim.utils.combiners import Combiner
from autoscalingsim.utils.error_check import ErrorChecker

class Adjuster(ABC):

    _Registry = {}

    def __init__(self, adjustment_horizon : dict, cooldown_period : dict, scaling_model : ScalingModel,
                 services_resource_requirements : dict, combiner_settings : dict,
                 calc_conf : 'DesiredPlatformAdjustmentCalculatorConfig', score_calculator_class : ScoreCalculator, node_groups_registry : 'NodeGroupsRegistry'):

        self.scaling_model = scaling_model
        self.services_resource_requirements = services_resource_requirements
        self.scorer = Scorer(score_calculator_class())

        adjustment_horizon_value = ErrorChecker.key_check_and_load('value', adjustment_horizon, self.__class__.__name__)
        adjustment_horizon_unit = ErrorChecker.key_check_and_load('unit', adjustment_horizon, self.__class__.__name__)
        self.adjustment_horizon = pd.Timedelta(adjustment_horizon_value, unit = adjustment_horizon_unit)

        cooldown_period_value = ErrorChecker.key_check_and_load('value', cooldown_period, self.__class__.__name__)
        cooldown_period_unit = ErrorChecker.key_check_and_load('unit', cooldown_period, self.__class__.__name__)
        self.cooldown_period = pd.Timedelta(cooldown_period_value, unit = cooldown_period_unit)

        combiner_type = ErrorChecker.key_check_and_load('type', combiner_settings, self.__class__.__name__)
        combiner_conf = ErrorChecker.key_check_and_load('conf', combiner_settings, self.__class__.__name__)
        self.combiner = Combiner.get(combiner_type)(combiner_conf)

        self.desired_change_calculator = DesiredPlatformAdjustmentCalculator(self.scorer, services_resource_requirements, calc_conf, node_groups_registry)

    def adjust_platform_state(self, cur_timestamp : pd.Timestamp, services_scaling_events : dict,
                              current_state : PlatformState, last_scheduled_scaling_action_ts : pd.Timestamp):

        print(f'cur_timestamp: {cur_timestamp}')

        timeline_of_deltas = DeltaTimeline(self.scaling_model, current_state)

        timeline_of_unmet_changes = TimelineOfDesiredServicesChanges(self.adjustment_horizon, self.combiner, services_scaling_events, cur_timestamp)

        ts_of_unmet_change, unmet_change = timeline_of_unmet_changes.next()

        in_work_state = current_state

        while not unmet_change is None and not ts_of_unmet_change is None:

            if ts_of_unmet_change >= cur_timestamp:

                unmet_change = self._attempt_to_use_existing_nodes_and_scale_down_if_needed(in_work_state, ts_of_unmet_change, unmet_change, timeline_of_deltas, last_scheduled_scaling_action_ts)

                if len(unmet_change) > 0:

                    # TODO: add test that ensures that timeline_of_deltas is unchanged
                    in_work_state, unmet_change_state, state_duration = self._roll_out_enforced_updates_temporarily(in_work_state, ts_of_unmet_change, unmet_change, timeline_of_deltas, timeline_of_unmet_changes)

                    state_addition_delta, state_score_addition = self._evaluate_nodes_addition_option(in_work_state, unmet_change_state, state_duration)
                    state_substitution_delta, state_score_substitution = self._evaluate_nodes_substitution_option(in_work_state, ts_of_unmet_change, unmet_change_state, state_duration)

                    self._update_timeline_with_best_option(timeline_of_deltas, ts_of_unmet_change, state_addition_delta, state_score_addition, state_substitution_delta, state_score_substitution, last_scheduled_scaling_action_ts)

            ts_of_unmet_change, unmet_change = timeline_of_unmet_changes.next()

        return timeline_of_deltas if timeline_of_deltas.updated_at_least_once else None

    def _attempt_to_use_existing_nodes_and_scale_down_if_needed(self, in_work_state : PlatformState, ts_of_unmet_change : pd.Timestamp,
                                                                unmet_change : dict, timeline_of_deltas_ref : DeltaTimeline, last_scheduled_scaling_action_ts : pd.Timestamp):

        in_work_state_delta, unmet_change = in_work_state.compute_soft_adjustment(unmet_change, self.services_resource_requirements)

        if self.cooldown_period > pd.Timedelta(0, unit = 's'):
            if last_scheduled_scaling_action_ts > ts_of_unmet_change:
                ts_of_unmet_change = last_scheduled_scaling_action_ts + self.cooldown_period
            else:
                time_to_be_elapsed_since_last_platform_update = ts_of_unmet_change - last_scheduled_scaling_action_ts
                if time_to_be_elapsed_since_last_platform_update > self.cooldown_period:
                    ts_of_unmet_change += (time_to_be_elapsed_since_last_platform_update - self.cooldown_period)

        timeline_of_deltas_ref.add_state_delta(ts_of_unmet_change, in_work_state_delta)

        return unmet_change

    def _roll_out_enforced_updates_temporarily(self, in_work_state : PlatformState, ts_of_unmet_change : pd.Timestamp, unmet_change : dict,
                                               timeline_of_deltas_ref : DeltaTimeline, timeline_of_unmet_changes_ref : TimelineOfDesiredServicesChanges):

        #tmp_timeline_of_deltas = deepcopy(timeline_of_deltas_ref)
        #new_in_work_state = tmp_timeline_of_deltas.roll_out_updates(ts_of_unmet_change) # TODO: NONE!!
        #if not new_in_work_state is None:
        #    in_work_state = new_in_work_state

        ts_next = timeline_of_unmet_changes_ref.peek(ts_of_unmet_change)
        state_duration = ts_next - ts_of_unmet_change
        unmet_change_state = GroupOfServicesRegionalized(unmet_change, self.services_resource_requirements)

        return (in_work_state, unmet_change_state, state_duration)

    def _evaluate_nodes_addition_option(self, in_work_state : PlatformState, unmet_change_state : GroupOfServicesRegionalized,
                                        state_duration : pd.Timedelta):

        state_addition_delta, state_score_addition = self.desired_change_calculator.compute_adjustment(unmet_change_state, state_duration)

        state_score_addition += self.scorer.score_platform_state(in_work_state, StateDuration.from_single_value(state_duration))

        return (state_addition_delta, state_score_addition)

    def _evaluate_nodes_substitution_option(self, in_work_state : PlatformState, ts_of_unmet_change : pd.Timestamp,
                                            unmet_change_state : GroupOfServicesRegionalized, state_duration : pd.Timedelta):

        in_work_collective_services_states = in_work_state.collective_services_states
        in_work_collective_services_states += unmet_change_state
        state_substitution_delta, state_score_substitution = self.desired_change_calculator.compute_adjustment(in_work_collective_services_states, state_duration)

        till_state_substitution = state_substitution_delta.till_full_enforcement(self.scaling_model, ts_of_unmet_change)

        state_score_substitution += self.scorer.score_platform_state(in_work_state, till_state_substitution)

        return (state_substitution_delta, state_score_substitution)

    def _update_timeline_with_best_option(self, timeline_of_deltas_ref : DeltaTimeline, ts_of_unmet_change : pd.Timestamp,
                                          state_addition_delta, state_score_addition,
                                          state_substitution_delta, state_score_substitution, last_scheduled_scaling_action_ts : pd.Timestamp):

        print(f'ts_of_unmet_change BEFORE: {ts_of_unmet_change}')
        print(f'last_scaling_action_ts: {last_scheduled_scaling_action_ts}')
        if self.cooldown_period > pd.Timedelta(0, unit = 's'):
            if last_scheduled_scaling_action_ts > ts_of_unmet_change:
                ts_of_unmet_change = last_scheduled_scaling_action_ts + self.cooldown_period
            else:
                time_to_be_elapsed_since_last_platform_update = ts_of_unmet_change - last_scheduled_scaling_action_ts
                if time_to_be_elapsed_since_last_platform_update > self.cooldown_period:
                    ts_of_unmet_change += (time_to_be_elapsed_since_last_platform_update - self.cooldown_period)
        print(f'ts_of_unmet_change AFTER: {ts_of_unmet_change}')
        if state_score_addition.is_worst:
            timeline_of_deltas_ref.add_state_delta(ts_of_unmet_change, state_substitution_delta) # TODO: add cooldown
        elif state_score_substitution.is_worst:
            timeline_of_deltas_ref.add_state_delta(ts_of_unmet_change, state_addition_delta)
        else:
            chosen_state_delta = state_addition_delta if state_score_addition.joint_score > state_score_substitution.joint_score else state_substitution_delta
            timeline_of_deltas_ref.add_state_delta(ts_of_unmet_change, chosen_state_delta)

    @classmethod
    def register(cls, name : str):

        def decorator(adjuster_class):
            cls._Registry[name] = adjuster_class
            return adjuster_class

        return decorator

    @classmethod
    def get(cls, name : str):

        if not name in cls._Registry:
            raise ValueError(f'An attempt to use a non-existent {cls.__name__} {name}')

        return cls._Registry[name]

from .adjusters_impl import *

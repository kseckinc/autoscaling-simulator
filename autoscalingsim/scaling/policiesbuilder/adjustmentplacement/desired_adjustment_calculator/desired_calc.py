import pandas as pd

import .optimizers
from .placer import Placer
from .scorer import Scorer, StateScore

from .....utils.state.region import Region
from .....utils.state.platform_state import PlatformState
from .....utils.state.entity_state.entities_states_reg import EntitiesStatesRegionalized

class DesiredChangeCalculator:

    """
    Implements PSO (Place-Score-Optimize) process. Provides the desired state
    of container groups that can further be used to compute deltas.
    """

    def __init__(self,
                 placement_hint : str,
                 score_calculator_class : score_calculators.ScoreCalculator,
                 optimizer_type : str,
                 container_for_scaled_entities_types : dict,
                 scaled_entity_instance_requirements_by_entity : dict):

        self.placer = Placer(placement_hint)
        score_calculator = score_calculator_class(container_for_scaled_entities_types)
        self.scorer = Scorer(score_calculator)
        optimizer_class = optimizers.Registry.get(optimizer_type)
        self.optimizer = optimizer_class()

        self.container_for_scaled_entities_types = container_for_scaled_entities_types
        self.scaled_entity_instance_requirements_by_entity = scaled_entity_instance_requirements_by_entity

    def __call__(self,
                 entities_states : EntitiesStatesRegionalized,
                 state_duration_h : float):

        # TODO: add logic to check whether empty results are returned
        regions = {}
        scores_per_region = {}
        joint_score = self.scorer.get_null_score()
        for region_name, entities_state in entities_states:
            # Place
            placements_lst = self.placer.compute_containers_requirements(self.scaled_entity_instance_requirements_by_entity,
                                                                         entities_state)
            # Score
            scored_placements_lst = self.scorer(placements_lst, state_duration_h)

            # Optimize
            selected_placement = self.optimizer(scored_placements_lst)

            regions[region_name] = Region(region_name,
                                          self.container_for_scaled_entities_types,
                                          self.scaled_entity_instance_requirements_by_entity,
                                          selected_placement)

            scores_per_region[region] = selected_placement.score

        # Building the new state based on the selected container type
        desired_state = PlatformState(regions)
        desired_deltas = desired_state.to_deltas()

        return (desired_deltas, StateScore(scores_per_region))
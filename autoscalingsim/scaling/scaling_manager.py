import pandas as pd

from .scaling_aspects import ScalingAspect

from autoscalingsim.state.platform_state import PlatformState
from autoscalingsim.state.node_group_state.node_group import HomogeneousNodeGroup

class ScalingManager:

    """
    Acts as an access point to the scaled services. Deals with the modification
    of the scaling-related properties and issuing desired state calculation.
    """

    def __init__(self, services_dict = None):

        self.services = services_dict if not services_dict is None else {}

    def add_source(self, service_ref):

        if not service_ref.name in self.services: self.services[service_ref.name] = service_ref

    def set_deployments(self, platform_state : PlatformState):

        """
        Sets multiple deployments acquired from the platform state provided as
        an argument to the call.
        """

        # Enforces scaling aspects values on scaled services
        scaling_infos = platform_state.extract_node_groups(False)
        for region_name, regional_node_groups in scaling_infos.items():
            for node_group in regional_node_groups:
                for service_name in node_group.get_running_services():
                    self.update_placement(service_name, region_name, node_group)

    def mark_groups_for_removal(self, service_name : str,
                                node_groups_ids_mark_for_removal_regionalized : dict):

        if not service_name in self.services:
            raise ValueError(f'An attempt to mark groups for removal for {service_name} that is unknown to {self.__class__.__name__}')

        for region_name, node_group_ids in node_groups_ids_mark_for_removal_regionalized.items():
            self.services[service_name].state.prepare_groups_for_removal(region_name, node_group_ids)

    def remove_groups_for_region(self, region_name : str, node_groups_ids : list):

        for service in self.services.values():
            service.state.force_remove_groups(region_name, node_groups_ids)

    def update_placement(self, service_name : str, region_name : str,
                         node_group : HomogeneousNodeGroup):

        """
        This method of the Scaling Manager is used by the Enforce step in the
        scaling policy -- it is used to set the decided upon value of the placement
        of the services that incorporates the count of nodes and information about them.
        """

        if not service_name in self.services:
            raise ValueError(f'An attempt to set the placement of {service_name} that is unknown to {self.__class__.__name__}')

        self.services[service_name].state.update_placement(region_name, node_group)

    def compute_desired_state(self):

        """
        Computes the desired regionalized services state for every scaled service managed by the Scaling
        Manager. The results for individual services are then aggregated into the joint timeline.
        Two services state get aggregated only if they occur at the same timestamp.
        """

        joint_timeline_desired_regionalized_services_states = {}
        for service_name, service_ref in self.services.items():
            service_timeline = service_ref.reconcile_desired_state()
            for timestamp, state_regionalized in service_timeline.items():
                if not timestamp in joint_timeline_desired_regionalized_services_states:
                    joint_timeline_desired_regionalized_services_states[timestamp] = state_regionalized
                else:
                    joint_timeline_desired_regionalized_services_states[timestamp] += state_regionalized

        return joint_timeline_desired_regionalized_services_states
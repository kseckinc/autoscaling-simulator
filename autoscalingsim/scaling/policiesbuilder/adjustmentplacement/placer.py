from collections import OrderedDict

class InContainerPlacement:

    """
    Wraps the information about the in-container placement. In case of nodes,
    it will be an in-node placement of services.

    Specifies:
        container type
        capacity taken
        scaled entities and their instance counts that can fit into this placement
    """

    def __init__(self,
                 container_type = None,
                 capacity_taken = 0,
                 placed_entities = 0):

        self.container_type = container_type
        self.capacity_taken = capacity_taken
        self.placed_entities = placed_entities

class Placer:

    """
    Proposes services placement options for each node type. These proposals
    are used as constraints by Adjuster, i.e. it can only use the generated
    proposals to search for a needed platform adjustment sufficing to its goal.
    TODO: Placer uses both static and dynamic information to form its proposals.
    In respect to the dynamic information, it can use the runtime utilization and
    performance information to adjust placement space. For instance, a service
    may strive for more memory than it is written in its resource requirements.
    """

    placement_hints = [
        'specialized',
        'balanced',
        'existing_mixture' # try to use an existig mixture of services on nodes if possible
    ]

    def __init__(self,
                 placement_hint = 'specialized'):

        if not placement_hint in Placer.placement_hints:
            raise ValueError('Adjustment preference {} currently not supported in {}'.(placement_hint, self.__class__.__name__))

        self.placement_hint = placement_hint
        self.cached_placement_options = {}
        self.balancing_threshold = 0.05 # TODO: consider providing in config file

    def compute_placement_options(self,
                                  scaled_entity_instance_requirements_by_entity,
                                  container_for_scaled_entities_types,
                                  dynamic_current_placement = None,
                                  dynamic_performance = None,
                                  dynamic_resource_utilization = None):
        """
        Wraps the placement options computation algorithm.
        The algorithm tries to determine the placement options according to the
        the placement hint given. If the placement according to the given hint
        does not succeed, Placer proceeds to the try more relaxed hints to
        generate the in-node placement constraints (options). The default last
        resort for Placer is the 'specialized' placement, i.e. single scaled
        entity instance per container for scaled entities.
        """

        # Using the cached results if no dynamic information is provided
        if (len(self.cached_placement_options) > 0) and (dynamic_current_placement is None) \
         and (dynamic_performance is None) and (dynamic_resource_utilization is None):
            return self.cached_placement_options

        placement_options = {}
        option_failed = False
        if self.placement_hint == 'existing_mixture':
            placement_options = self._place_existing_mixture(scaled_entity_instance_requirements_by_entity,
                                                             container_for_scaled_entities_types,
                                                             dynamic_current_placement,
                                                             dynamic_performance,
                                                             dynamic_resource_utilization)
            if len(placement_options) > 0:
                return placement_options
            else:
                option_failed = True

        if option_failed or (self.placement_hint == 'balanced'):
            option_failed = False
            placement_options = self._place_shared(scaled_entity_instance_requirements_by_entity,
                                                   container_for_scaled_entities_types,
                                                   dynamic_performance,
                                                   dynamic_resource_utilization)

            if self.placement_hint == 'balanced':
                placement_options = self._place_balanced(placement_options)

            if len(placement_options) > 0:
                return placement_options
            else:
                option_failed = True

        if option_failed or (self.placement_hint == 'specialized'):
            option_failed = False
            placement_options = self._place_specialized(scaled_entity_instance_requirements_by_entity,
                                                        container_for_scaled_entities_types,
                                                        dynamic_performance,
                                                        dynamic_resource_utilization)
            if len(placement_options) > 0:
                return placement_options
            else:
                option_failed = True

        self.cached_placement_options = placement_options

        return placement_options

    def _place_existing_mixture(self,
                                scaled_entity_instance_requirements_by_entity,
                                container_for_scaled_entities_types,
                                dynamic_current_placement,
                                dynamic_performance = None,
                                dynamic_resource_utilization = None):
        return {}

    def _place_shared(self,
                      scaled_entity_instance_requirements_by_entity,
                      container_for_scaled_entities_types,
                      dynamic_performance = None,
                      dynamic_resource_utilization = None):

        placement_options = {}
        for container_name, container_info in container_for_scaled_entities_types.items():
            # For each scaled entity compute how much of container does it consume
            container_capacity_taken_by_entity = {}
            for scaled_entity, instance_requirements in scaled_entity_instance_requirements_by_entity.items():
                fits, cap_taken = container_info.takes_capacity({scaled_entity: instance_requirements})
                if fits:
                    container_capacity_taken_by_entity[scaled_entity] = cap_taken

            # Sort in decreasing order of consumed container capacity
            container_capacity_taken_by_entity_sorted = OrderedDict(reversed(sorted(container_capacity_taken_by_entity.items(),
                                                                                    key = lambda elem: elem[1])))

            # Take first in list, and try to add the others to it (maybe with multipliers),
            # then take the next one and try the rest of the sorted list and so on
            placement_options_per_container = []
            considered = []
            for entity_name in container_capacity_taken_by_entity_sorted.keys():

                further_container_capacity_taken = { entity_name: capacity for entity_name, capacity in container_capacity_taken_by_entity_sorted.items() if not entity_name in considered }
                single_placement_option_instances = {}
                cumulative_capacity = SystemCapacity(container_name)
                instances_count = 0

                for entity_name_to_consider, capacity_to_consider in further_container_capacity_taken.items():
                    while not cumulative_capacity.is_exhausted():
                        cumulative_capacity += capacity_to_consider
                        instances_count += 1

                    cumulative_capacity -= capacity_to_consider
                    instances_count -= 1
                    single_placement_option_instances[entity_name_to_consider] = instances_count

                single_placement_option = InContainerPlacement(container_name,
                                                               cumulative_capacity,
                                                               single_placement_option_instances)

                placement_options_per_container.append(single_placement_option)
                considered.append(entity_name)

            if len(placement_options_per_container) > 0:
                placement_options[container_name] = placement_options_per_container

        return placement_options

    def _place_balanced(self,
                        shared_placement_options,
                        scaled_entity_instance_requirements_by_entity = None,
                        container_for_scaled_entities_types = None,
                        dynamic_performance = None,
                        dynamic_resource_utilization = None):


        # Select the most balanced options by applying the threshold.
        balanced_placement_options = {}
        for container_name, placement_options_per_container in shared_placement_options.items():
            balanced_placement_options_per_container = []
            best_placement_option_so_far = InContainerPlacement()

            for single_placement_option in placement_options_per_container:

                if abs(single_placement_option.capacity_taken.collapse() - 1) <= self.balancing_threshold:
                    balanced_placement_options_per_container.append(single_placement_option)

                if abs(single_placement_option.capacity_taken.collapse() - 1) < \
                 abs(best_placement_option_so_far.capacity_taken.collapse() - 1):
                    best_placement_option_so_far = single_placement_option

            # Fallback option: taking the best-balanced solution so far, but not within the balancing threshold
            if len(balanced_placement_options_per_container) == 0:
                balanced_placement_options_per_container.append(best_placement_option_so_far)

        return balanced_placement_options_per_container

    def _place_specialized(self,
                           scaled_entity_instance_requirements_by_entity,
                           container_for_scaled_entities_types,
                           dynamic_performance = None,
                           dynamic_resource_utilization = None):
        pass
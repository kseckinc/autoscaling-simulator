import os
import pandas as pd

from .adjustmentplacement.adjustment_policy import AdjustmentPolicy

class ScalingPolicy:

    """
    Defines the general structure of the scaling policy according to SCAPE process
    as comprising the steps:

    - Scale:   this step governs scaling of the services; to a large extent, it defines
               the inputs to the succeeding steps.
    - Combine: this step defines how the scaled service instances can be combined
               according to a particilar goal. For instance, the instances can be
               combined based on whether they form the resource bottleneck or not,
               i.e. two service instances are bundled together if one requires way more
               memory than the other, whereas the other is more CPU-hungry. A fallback
               combination is one service instance per node. Better: produce several
               combinations that can be used as a sequence of fallback options by the
               next stage. Or allow the Adjust step to return to the Combine step
               if the proposed combination is not feasible for the infrastructure.
    - Adjust:  this step does the follow-up scaling of the virtual infrastructure
               (cluster) s.t. the combinations of scaled service instances can be
               accommodated on the nodes. Particular optimization goals may be added
               on this step, e.g. minimizing the cost of the accommodation, or the
               utilization of the nodes.
    - Place:   this step builds the mapping of the scaled  services onto the nodes
               based on the labels that restrict the placement of services onto
               the nodes. For instance, the service may require a particular type
               of hardware (say, GPU) to process the workload or should be placed
               in a particular geographical region.
    - Enforce: enforce the results of the above steps by updating the shared state
               that will be read by each service and the infrastructure at the end
               of the simulation step.

    """

    class ScalingState:

        def __init__(self):

            self.last_sync_timestamp = pd.Timestamp(0)

        def get_val(self,
                    attribute_name):

            if not hasattr(self, attribute_name):
                raise ValueError('Attribute {} not found in {}'.format(attribute_name, self.__class__.__name__))

            return self.__getattribute__(attribute_name)

        def update_val(self,
                       attribute_name,
                       attribute_val):

            if not hasattr(self, attribute_name):
                raise ValueError('Untimed attribute {} not found in {}'.format(aspect_name, self.__class__.__name__))

            self.__setattr__(aspect_name, aspect_val)

    def __init__(self,
                 config_file,
                 scaling_model,
                 platform_model):

        self.scaling_manager = None
        self.scaling_settings = None
        self.platform_model = platform_model

        self.state = ScalingPolicy.ScalingState()

        if not os.path.isfile(config_file):
            raise ValueError('No {} configuration file found under the path {}'.format(self.__class__.__name__, config_file))
        else:
            self.scaling_settings = ScalingPolicyConfiguration(config_file)
            adjustment_policy = AdjustmentPolicy(scaling_model,
                                                 self.scaling_settings)
            self.platform_model.set_adjustment_policy(adjustment_policy)

    def reconcile_state(self,
                        cur_timestamp):

        if (cur_timestamp - self.state.get_val('last_sync_timestamp')) > self.scaling_settings.sync_period_timedelta:

            # Scale -> scaling services to accomodate the workload
            desired_states_to_process = {}
            if not self.scaling_manager is None:
                desired_states_to_process = self.scaling_manager.compute_desired_state()

            if len(desired_states_to_process) > 0:
                # TODO: Combine -> scaling app as a whole to remove bottlenecks

                # Adjust /w placement constraints -> adjusting the platform
                # to the demands of the scaled app while taking into account
                # adjustment goals such as minimization of the cost of the
                # platform resources used and obeying the placement constraints.
                self.platform_model.adjust(cur_timestamp,
                                           desired_states_to_process)

            # Updating the timestamp of the last state reconciliation
            self.state.update_val('last_sync_timestamp', cur_timestamp)

        # Enforce use scaling_aspect_manager
        # this part goes independent of the sync period since it's about
        # implementing the scaling decision which is e.g. in desired state, not taking it
        if not self.scaling_manager is None:
            pass # TODO: remember updating platform_threads_available in the service state

    def get_services_scaling_settings(self):

        return self.scaling_settings.services_scaling_config

    def set_scaling_manager(self,
                            scaling_manager):

        self.scaling_manager = scaling_manager

    def set_state_reader(self,
                         state_reader):

        self.state_reader = state_reader
        #self.adjustment_policy.set_state_reader(state_reader)
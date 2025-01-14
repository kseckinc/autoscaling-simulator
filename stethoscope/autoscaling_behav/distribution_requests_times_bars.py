import os
import collections
import numpy as np
import matplotlib.ticker as ticker
from matplotlib import pyplot as plt

import stethoscope.plotting_constants as plotting_constants

class DistributionRequestsTimesBarchart:

    FILENAME = 'bars_req_time_distribution_by_cat.png'

    @classmethod
    def comparative_plot(cls: type, simulations_by_name : dict, bar_width : float = 0.25, figures_dir : str = None, names_converter = None):

        req_types = list()
        response_times_regionalized_aggregated = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
        network_times_regionalized_aggregated = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
        buffer_times_regionalized_aggregated = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
        for simulation_name, simulation_instances in simulations_by_name.items():

            for simulation in simulation_instances:
                for region_name, response_times_per_request_type in simulation.response_times.items():
                    for req_type, response_times in response_times_per_request_type.items():
                        req_types.append(req_type)
                        response_times_regionalized_aggregated[region_name][req_type][simulation_name].extend(response_times)

                for region_name, network_times_per_request_type in simulation.network_times.items():
                    for req_type, network_times in network_times_per_request_type.items():
                        network_times_regionalized_aggregated[region_name][req_type][simulation_name].extend(network_times)

                for region_name, buffer_times_per_request_type in simulation.buffer_times.items():
                    for req_type, buffer_times_per_service in buffer_times_per_request_type.items():
                        for service_name, buffer_times in buffer_times_per_service.items():
                            buffer_times_regionalized_aggregated[region_name][req_type][simulation_name].extend(buffer_times)

        for region_name, response_times_per_request_type in response_times_regionalized_aggregated.items():
            fig, axs = plt.subplots(1, len(set(req_types)), figsize = (4, 3), sharey = True)
            if not isinstance(axs, collections.Iterable):
                axs = np.asarray([axs])

            network_times_per_request_type = network_times_regionalized_aggregated[region_name] if region_name in network_times_regionalized_aggregated else dict()
            buffer_times_per_request_type = buffer_times_regionalized_aggregated[region_name] if region_name in buffer_times_regionalized_aggregated else dict()
            cls._internal_plot(axs, response_times_per_request_type, network_times_per_request_type, buffer_times_per_request_type, bar_width, names_converter = names_converter)
            cls._internal_post_processing(region_name, figures_dir)

    @classmethod
    def _internal_plot(cls : type, axs, response_times_per_request_type : dict, network_times_per_request_type : dict, buffer_times_per_request_type : dict, bar_width : float, names_converter = None):

        for ax in axs.flatten():
            for req_type, response_times_per_alternative in response_times_per_request_type.items():

                processing_times_per_alternative_sum = list()
                network_times_per_alternative_sum = list()
                buffer_times_per_alternative_sum = list()

                for simulation_name, response_times in response_times_per_alternative.items():
                    total_response_time = sum(response_times) if len(response_times) > 0 else 0

                    network_times_per_alternative = network_times_per_request_type[req_type] if req_type in network_times_per_request_type else dict()
                    network_times = network_times_per_alternative[simulation_name] if simulation_name in network_times_per_alternative else list()
                    total_network_time = sum(network_times) if len(network_times) > 0 else 0

                    buffer_times_per_alternative = buffer_times_per_request_type[req_type] if req_type in buffer_times_per_request_type else dict()
                    buffer_times = buffer_times_per_alternative[simulation_name] if simulation_name in buffer_times_per_alternative else list()
                    total_buffer_time = sum(buffer_times) if len(buffer_times) > 0 else 0

                    network_times_per_alternative_sum.append((total_network_time / total_response_time) * 100)
                    buffer_times_per_alternative_sum.append((total_buffer_time / total_response_time) * 100)
                    total_processing_time = total_response_time - (total_network_time + total_buffer_time)
                    processing_times_per_alternative_sum.append((total_processing_time / total_response_time) * 100)

                labels = [ names_converter(simulation_name, split_policies = True) for simulation_name in response_times_per_alternative.keys() ]
                y = np.arange(len(labels))

                ax.barh(y, processing_times_per_alternative_sum, bar_width, label = 'Processing')
                ax.barh(y, network_times_per_alternative_sum, bar_width, left = processing_times_per_alternative_sum, label = 'Transferring')
                ax.barh(y, buffer_times_per_alternative_sum, bar_width, left = np.array(processing_times_per_alternative_sum) + np.array(network_times_per_alternative_sum), label = 'Waiting')
                ax.set_yticks(y)
                ax.set_yticklabels(labels)
                ax.set_title(f'Request {req_type}')
                ax.legend(loc = 'center left', bbox_to_anchor = (1.05, 0.5))
                ax.set_xlabel('Time spent in status, %')

    @classmethod
    def _internal_post_processing(cls : type, region_name : str, figures_dir : str = None):

        if not figures_dir is None:
            figure_path = os.path.join(figures_dir, plotting_constants.filename_format.format(region_name, cls.FILENAME))
            plt.savefig(figure_path, dpi = plotting_constants.PUBLISHING_DPI, bbox_inches = 'tight')
        else:
            plt.suptitle(f'Distribution of the request time in the application in region {region_name}')
            plt.show()

        plt.close()

    @classmethod
    def plot(cls : type,
             response_times_regionalized : dict,
             buffer_times_regionalized : dict,
             network_times_regionalized : dict,
             aggregation_fn = np.mean,
             bar_width : float = 0.15,
             figures_dir : str = None):

        """
        Barchart of the processing vs waiting vs network time
        for the fulfilled requests, a bar for each request type
        """

        if not callable(aggregation_fn):
            raise ValueError('The aggregation function object is not callable.')

        for region_name, response_times_per_request_type in response_times_regionalized.items():
            present_request_types_cnt = len([ True for resp_times in response_times_per_request_type.values() if len(resp_times) > 0 ])

            if present_request_types_cnt > 0:
                fig, ax = plt.subplots(nrows = 1, ncols = 1, figsize = (plotting_constants.SQUARE_PLOT_SIDE_INCH * present_request_types_cnt, plotting_constants.SQUARE_PLOT_SIDE_INCH))
                buffer_times_by_request = buffer_times_regionalized[region_name]
                network_times_by_request = network_times_regionalized[region_name]

                aggregated_processing_time_per_req_type = []
                aggregated_buf_waiting_time_per_req_type = []
                aggregated_network_time_per_req_type = []

                for req_type in response_times_per_request_type.keys():

                    req_type_response_times = response_times_per_request_type[req_type]
                    req_type_network_times = network_times_by_request[req_type] if req_type in network_times_by_request else [0.0]
                    aggregated_network_time_per_req_type.append(aggregation_fn(req_type_network_times))

                    req_type_buf_waiting_times = [0.0]
                    if req_type in buffer_times_by_request:
                        req_type_buf_waiting_times = []
                        if isinstance(buffer_times_by_request[req_type], collections.Mapping):
                            for buf_wait_time_per_service in buffer_times_by_request[req_type].values():
                                req_type_buf_waiting_times.extend(list(buf_wait_time_per_service))

                    aggregated_buf_waiting_time_per_req_type.append(aggregation_fn(req_type_buf_waiting_times))

                    agg_proc_time = aggregation_fn(req_type_response_times) - (aggregated_buf_waiting_time_per_req_type[-1] + aggregated_network_time_per_req_type[-1])
                    aggregated_processing_time_per_req_type.append(agg_proc_time)

                req_types = [ f'{req_type[:plotting_constants.VARIABLE_NAMES_SIZE_LIMIT]}...' for req_type in response_times_per_request_type.keys() ]
                ax.bar(req_types, aggregated_processing_time_per_req_type, bar_width, label='Processing')
                ax.bar(req_types, aggregated_network_time_per_req_type,
                       bar_width, bottom = aggregated_processing_time_per_req_type, label='Transferring')

                ax.bar(req_types, aggregated_buf_waiting_time_per_req_type,
                       bar_width, bottom = np.array(aggregated_processing_time_per_req_type) \
                                            + np.array(aggregated_network_time_per_req_type), label='Waiting')

                ax.set_ylabel('Duration, ms')
                ax.legend(loc = 'lower center', bbox_to_anchor = (0.5, -0.3), ncol = 3)

                major_ticks_interval_raw = int(ax.get_ylim()[1] / (plotting_constants.SQUARE_PLOT_SIDE_INCH * plotting_constants.MAJOR_TICKS_PER_INCH))
                major_ticks_interval = round(major_ticks_interval_raw, -max(len(str(major_ticks_interval_raw)) - 2, 0))
                minor_ticks_interval = major_ticks_interval // plotting_constants.MINOR_TICKS_PER_MAJOR_TICK_INTERVAL

                ax.yaxis.set_major_locator(ticker.MultipleLocator(major_ticks_interval))
                ax.yaxis.set_minor_locator(ticker.MultipleLocator(minor_ticks_interval))

                fig.tight_layout()

                if not figures_dir is None:
                    figure_path = os.path.join(figures_dir, plotting_constants.filename_format.format(region_name, cls.FILENAME))
                    plt.savefig(figure_path, dpi = plotting_constants.PUBLISHING_DPI, bbox_inches='tight')
                else:
                    plt.suptitle(f'Distribution of the request time in the application,\
                    \naggregated with the {aggregation_fn.__name__} function in region {region_name}')
                    plt.show()

                plt.close()

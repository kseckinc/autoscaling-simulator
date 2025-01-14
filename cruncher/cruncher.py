import os
import glob
import json
import collections
import pandas as pd
import numpy as np
import prettytable
import pickle
from prettytable import PrettyTable

from stethoscope.analytical_engine import AnalysisFramework
from autoscalingsim.simulator import Simulator
from autoscalingsim.infrastructure_platform.platform_model import PlatformModel
from autoscalingsim.utils.error_check import ErrorChecker

from .experimental_regime.experimental_regime import ExperimentalRegime

def convert_name_of_considered_alternative_to_label(original_string : str, split_policies : bool = False):

    s = '['
    ss = original_string.split(ExperimentalRegime._policies_categories_delimiter)[1:]
    for policy_raw in ss[:-1]:
        k = policy_raw.split(ExperimentalRegime._concretization_delimiter)
        s += f'{k[0]} -> {k[1]}; '
        if split_policies:
            s += '\n'

    k = ss[-1].split(ExperimentalRegime._concretization_delimiter)
    s += f'{k[0]} -> {k[1]}]'

    return s

class Cruncher:

    """ """

    def __init__(self, config_folder : str = None):

        if not os.path.exists(config_folder):
            raise ValueError(f'Configuration folder {config_folder} does not exist')

        jsons_found = glob.glob(os.path.join(config_folder, '*.json'))
        if len(jsons_found) == 0:
            raise ValueError(f'No candidate JSON configuration files found in folder {config_folder}')

        config_file = jsons_found[0]
        with open(config_file) as f:
            try:
                config = json.load(f)

                experiment_config = ErrorChecker.key_check_and_load('experiment_config', config)
                self.persist_plots_for_individual_experiments = ErrorChecker.key_check_and_load('persist_plots_for_individual_experiments', experiment_config, default = False)
                regime = ErrorChecker.key_check_and_load('regime', experiment_config, default = None)
                if regime is None:
                    raise ValueError('You should specify the experimental regime: alternative_policies or building_blocks')

                repetitions_count_per_simulation = ErrorChecker.key_check_and_load('repetitions_count_per_simulation', experiment_config, default = 1)
                if repetitions_count_per_simulation == 1:
                    print('WARNING: There will be only a single repetition for each alternative evaluated since the parameter *repetitions_count_per_simulation* is set to 1')
                self.results_folder = ErrorChecker.key_check_and_load('results_folder', experiment_config)
                if not self.results_folder is None and not os.path.exists(self.results_folder):
                    os.makedirs(self.results_folder)

                store_raw_data = ErrorChecker.key_check_and_load('store_raw_data', experiment_config, default = True)
                self.path_to_store_data = os.path.join(self.results_folder, 'data') if store_raw_data is True else None
                if not self.path_to_store_data is None:
                    if not os.path.exists(self.path_to_store_data):
                        os.makedirs(self.path_to_store_data)

                keep_evaluated_configs = ErrorChecker.key_check_and_load('keep_evaluated_configs', experiment_config)

                simulation_config_raw = ErrorChecker.key_check_and_load('simulation_config', config)
                self.simulation_step = pd.Timedelta(**ErrorChecker.key_check_and_load('simulation_step', simulation_config_raw))
                simulation_config = { 'simulation_step': self.simulation_step,
                                      'starting_time': pd.Timestamp(ErrorChecker.key_check_and_load('starting_time', simulation_config_raw)),
                                      'time_to_simulate': pd.Timedelta(**ErrorChecker.key_check_and_load('time_to_simulate', simulation_config_raw)) }

                regime_config = ErrorChecker.key_check_and_load('regime_config', experiment_config)
                self.regime = ExperimentalRegime.get(regime)(config_folder, regime_config, Simulator(**simulation_config), repetitions_count_per_simulation, keep_evaluated_configs)

            except json.JSONDecodeError:
                raise ValueError(f'An invalid JSON when parsing for {self.__class__.__name__}')

    def run_experiment(self):

        self.regime.run_experiment(self.path_to_store_data)

    def set_data_dir(self, path_to_store_data : str):

        self.path_to_store_data = path_to_store_data

    def visualize(self):

        af = AnalysisFramework(self.simulation_step)

        simulations_results = collections.defaultdict(list)
        if self.path_to_store_data is None:
            simulations_results = self.regime.simulations_results

        else:
            for filename in os.listdir(self.path_to_store_data):
                sim_name_full = filename.split('.')[0]
                sim_name_pure = sim_name_full.split(ExperimentalRegime._simulation_instance_delimeter)[0]
                simulations_results[sim_name_pure].append(pickle.load(open(os.path.join(self.path_to_store_data, filename), 'rb')))

        for sim_id, sim_info in enumerate(simulations_results.items()):
            simulation_name, simulation_instances_results = sim_info[0], sim_info[1]

            for simulation_instance_results in simulation_instances_results:
                if self.persist_plots_for_individual_experiments:
                    simulation_figures_folder = os.path.join(self.results_folder, simulation_name, sim_id)
                    if not os.path.exists(simulation_figures_folder):
                        os.makedirs(simulation_figures_folder)

                    af.build_figures_for_single_simulation(simulation_instance_results, figures_dir = simulation_figures_folder)

        af.build_comparative_figures(simulations_results, figures_dir = self.results_folder, names_converter = convert_name_of_considered_alternative_to_label)

        summary_filepath = os.path.join(self.results_folder, 'summary.txt')
        header = ''.join(['-'] * 20) + ' SUMMARY CHARACTERISTICS OF EVALUATED ALTERNATIVES ' + ''.join(['-'] * 20)
        report_text = ''.join(['-'] * len(header)) + '\n' + header + '\n' + ''.join(['-'] * len(header)) + '\n\n'
        for idx, sim in enumerate(simulations_results.items(), 1):
            simulation_name, simulation_instances_results = sim[0], sim[1]

            total_cost_for_alternative = collections.defaultdict(lambda: collections.defaultdict(float))
            response_times_regionalized_aggregated = collections.defaultdict(lambda: collections.defaultdict(int))
            load_regionalized_aggregated = collections.defaultdict(lambda: collections.defaultdict(int))
            utilization_aggregated = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(float)))
            node_count_aggregated = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: {'avg': {'desired': 0.0, 'actual': 0.0}, 'std': {'desired': 0.0, 'actual': 0.0}})))
            resource_names = list()
            for simulation_instance_results in simulation_instances_results:
                for provider_name, cost_per_region in simulation_instance_results.infrastructure_cost.items():
                    for region_name, cost_in_time in cost_per_region.items():
                        total_cost_for_alternative[provider_name][region_name] += (cost_in_time[-1] / len(simulation_instances_results))

                for region_name, response_times_per_request_type in simulation_instance_results.response_times.items():
                    for req_type, response_times in response_times_per_request_type.items():
                        response_times_regionalized_aggregated[region_name][req_type] += len(response_times)

                for region_name, load_ts_per_request_type in simulation_instance_results.load.items():
                    for req_type, load_timeline in load_ts_per_request_type.items():
                        if len(load_timeline.value) > 0:
                            generated_req_cnt = sum(load_timeline.value)
                            if generated_req_cnt > 0:
                                load_regionalized_aggregated[region_name][req_type] += generated_req_cnt

                for service_name, utilization_per_region in simulation_instance_results.utilization.items():
                    for region_name, utilization_per_resource in utilization_per_region.items():
                        for resource_name, utilization_ts in utilization_per_resource.items():
                            resource_names.append(resource_name)
                            utilization_aggregated[service_name][region_name][resource_name] += (utilization_ts.value.mean() / len(simulation_instances_results))

                for provider_name, desired_node_count_per_region in simulation_instance_results.desired_node_count.items():
                    for region_name, desired_node_count_per_node_type in desired_node_count_per_region.items():
                        for node_type, desired_counts_raw in desired_node_count_per_node_type.items():
                            desired_count_avg = np.mean(desired_counts_raw[PlatformModel.node_count_key])
                            desired_count_std = np.std(desired_counts_raw[PlatformModel.node_count_key])
                            node_count_aggregated[provider_name][region_name][node_type]['avg']['desired'] += (desired_count_avg / len(simulation_instances_results))
                            node_count_aggregated[provider_name][region_name][node_type]['std']['desired'] += (desired_count_std / len(simulation_instances_results))

                            actual_counts_raw = simulation_instance_results.actual_node_count.get(provider_name, dict()).get(region_name, dict()).get(node_type, dict())
                            actual_count_avg = np.mean(actual_counts_raw[PlatformModel.node_count_key])
                            actual_count_std = np.std(actual_counts_raw[PlatformModel.node_count_key])
                            node_count_aggregated[provider_name][region_name][node_type]['avg']['actual'] += (desired_count_avg / len(simulation_instances_results))
                            node_count_aggregated[provider_name][region_name][node_type]['std']['actual'] += (desired_count_std / len(simulation_instances_results))


            report_text += f'Alternative {idx}: {convert_name_of_considered_alternative_to_label(simulation_name)}\n\n'
            report_text += f'>>> COST:\n'
            summary_cost_table = PrettyTable(['Provider', 'Region', 'Total cost, USD'])
            for provider_name, cost_per_region in total_cost_for_alternative.items():
                for region_name, total_cost in cost_per_region.items():
                    summary_cost_table.add_row([provider_name, region_name, round(total_cost, 5)])

            report_text += (str(summary_cost_table) + '\n\n')

            report_text += f'>>> REQUESTS THAT MET SLO:\n'
            summary_reqs_table = PrettyTable(['Region', 'Request type', 'Total generated', 'Met SLO (%)'])
            for region_name, generated_by_req_type in load_regionalized_aggregated.items():
                for req_type, generated_cnt in generated_by_req_type.items():
                    response_times_per_request_type = response_times_regionalized_aggregated[region_name] if region_name in response_times_regionalized_aggregated else dict()
                    met_slo_cnt = response_times_per_request_type[req_type] if req_type in response_times_per_request_type else 0
                    met_slo_percent = round((met_slo_cnt / generated_cnt) * 100, 2)
                    summary_reqs_table.add_row([region_name, req_type, generated_cnt, f'{met_slo_cnt} ({met_slo_percent})'])

            report_text += (str(summary_reqs_table) + '\n\n')

            report_text += f'>>> AVERAGE RESOURCE UTILIZATION:\n'
            resource_names = list(set(resource_names))
            resource_names_header = [ f'{res_name}, %' for res_name in resource_names ]
            summary_res_util_table = PrettyTable(['Service', 'Region'] + resource_names_header)
            for service_name, utilization_per_region in utilization_aggregated.items():
                for region_name, utilization_per_resource in utilization_per_region.items():
                    ordered_res_utils = [ round(utilization_per_resource[resource_name] * 100, 2) if resource_name in utilization_per_resource else 0.0 for resource_name in resource_names ]
                    summary_res_util_table.add_row([service_name, region_name] + ordered_res_utils)

            report_text += (str(summary_res_util_table) + '\n\n')

            report_text += f'>>> NODES USAGE BY TYPE:\n'
            summary_nodes_table = PrettyTable(['Provider', 'Region', 'Node type', 'Desired count avg (std)', 'Actual count avg (std)'])
            for provider_name, node_count_per_region in node_count_aggregated.items():
                for region_name, node_count_per_node_type in node_count_per_region.items():
                    for node_type, counts in node_count_per_node_type.items():
                        desired = f'{round(counts["avg"]["desired"], 2)} (\u00B1{round(counts["std"]["desired"], 5)})'
                        actual = f'{round(counts["avg"]["actual"], 2)} (\u00B1{round(counts["std"]["actual"], 5)})'
                        summary_nodes_table.add_row([provider_name, region_name, node_type, desired, actual])

            report_text += (str(summary_nodes_table) + '\n\n')

        with open(summary_filepath, 'w') as f:
            f.write(report_text)

import json
import numbers

from .metric.scalingmetric import MetricDescription
from .scaled.scaled_entity import ScaledEntityScalingSettings

from ...utils.error_check import ErrorChecker

class ScalingPolicyConfiguration:

    """
    Wraps the configuration of the scaling policy extracted from the configuration
    file.
    """

    def __init__(self,
                 config_file):

        self.app_structure_scaling_config = None
        self.services_scaling_config = {}
        self.platform_scaling_config = None

        with open(config_file) as f:
            try:
                config = json.load(f)

                policy_config = ErrorChecker.key_check_and_load('policy', config, self.__class__.__name__)
                app_config = ErrorChecker.key_check_and_load('application', config, self.__class__.__name__)
                platform_config = ErrorChecker.key_check_and_load('platform', config, self.__class__.__name__)

                # General policy settings
                self.sync_period_timedelta = pd.Timedelta(ErrorChecker.key_check_and_load('sync_period_ms', policy_config, self.__class__.__name__), unit = 'ms')
                self.adjustment_goal = ErrorChecker.key_check_and_load('adjustment_goal', policy_config, self.__class__.__name__)
                self.adjustment_preference = ErrorChecker.key_check_and_load('adjustment_preference', policy_config, self.__class__.__name__)

                structure_config = ErrorChecker.key_check_and_load('structure', app_config, self.__class__.__name__)
                services_config = ErrorChecker.key_check_and_load('services', app_config, self.__class__.__name__)

                # TODO: structure_config processing

                # Services settings
                for service_config in services_config:
                    service_key = 'service'
                    service_name = ErrorChecker.key_check_and_load(service_key, service_config, self.__class__.__name__)
                    scaled_entity_name = ErrorChecker.key_check_and_load('scaled_entity_name', service_config, service_key, service_name)
                    scaled_aspect_name = ErrorChecker.key_check_and_load('scaled_aspect_name', service_config, service_key, service_name)

                    metrics_descriptions = []
                    metric_descriptions_json = ErrorChecker.key_check_and_load('metrics_descriptions', service_config, service_key, service_name)
                    for metric_description_json in metric_descriptions_json:

                        metric_source_name = ErrorChecker.key_check_and_load('metric_source_name', metric_description_json, service_key, service_name)
                        metric_name = ErrorChecker.key_check_and_load('metric_name', metric_description_json, service_key, service_name)

                        # TODO: think of non-obligatory parameters that can be identified as none
                        values_filter_conf = self._conf_obj_check(metric_description_json,
                                                                  'values_filter_conf',
                                                                  ValuesFilter)
                        values_aggregator_conf = self._conf_obj_check(metric_description_json,
                                                                     'values_aggregator_conf',
                                                                      ValuesAggregator)
                        stabilizer_conf = self._conf_obj_check(metric_description_json,
                                                               'stabilizer_conf',
                                                               Stabilizer)
                        forecaster_conf = self._conf_obj_check(metric_description_json,
                                                               'forecaster_conf',
                                                               MetricForecaster)

                        capacity_adaptation_type = MetricDescription.config_check(metric_description_json,
                                                                                  'capacity_adaptation_type')
                        timing_type = MetricDescription.config_check(metric_description_json,
                                                                     'timing_type')

                        target_value = self._conf_numeric_check(metric_description_json,
                                                                'target_value',
                                                                1.0)
                        priority = self._conf_numeric_check(metric_description_json,
                                                            'priority')
                        initial_max_limit = self._conf_numeric_check(metric_description_json,
                                                                     'initial_max_limit')
                        initial_min_limit = self._conf_numeric_check(metric_description_json,
                                                                     'initial_min_limit')
                        initial_entity_representation_in_metric = self._conf_numeric_check(metric_description_json,
                                                                                           'initial_entity_representation_in_metric')

                        metric_descr = MetricDescription(scaled_entity_name,
                                                         scaled_aspect_name,
                                                         metric_source_name,
                                                         metric_name,
                                                         values_filter_conf,
                                                         values_aggregator_conf,
                                                         target_value,
                                                         stabilizer_conf,
                                                         timing_type,
                                                         forecaster_conf,
                                                         capacity_adaptation_type,
                                                         priority,
                                                         initial_max_limit,
                                                         initial_min_limit,
                                                         initial_entity_representation_in_metric)

                        metrics_descriptions.append(metric_descr)

                    scaling_effect_aggregation_rule_name = ErrorChecker.key_check_and_load('scaling_effect_aggregation_rule_name', service_config, service_key, service_name)
                    self.services_scaling_config[service_name] = ScaledEntityScalingSettings(metrics_descriptions,
                                                                                             scaling_effect_aggregation_rule_name,
                                                                                             scaled_entity_name,
                                                                                             scaled_aspect_name)

                # TODO: platform_config processing


            except json.JSONDecodeError:
                raise ValueError('The config file {} is an invalid JSON.'.format(config_file))

    def _conf_numeric_check(self,
                            metric_description_json,
                            conf_key,
                            default_value = 0):

        numeric_conf = default_value
        if conf_key in metric_description_json:
            numeric_conf = metric_description_json[conf_key]

            if not isinstance(numeric_conf, numbers.Number):
                raise ValueError('{} is not a number: {}'.format(conf_key, numeric_conf))

            if numeric_conf < 0:
                raise ValueError('{} should be positive or zero, provided: {}'.format(conf_key, numeric_conf))

        return numeric_conf

    def _conf_obj_check(self,
                        metric_description_json,
                        conf_key,
                        checker,
                        default_value = None):

        obj_conf = None
        if conf_key in metric_description_json:
            obj_conf = metric_description_json[conf_key]
            checker.config_check(obj_conf)

        return obj_conf
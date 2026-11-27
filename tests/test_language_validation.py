"""模型反馈不能获得答案，模板修正不能冒充模型正确。"""
import json
import unittest
from unittest.mock import patch
from backend.services.intelligence.language import decoded_fields, parse_description
from backend.services.intelligence.language_rules import grounded_fields


class LanguageValidationTests(unittest.TestCase):
    def test_memory_error_falls_back_to_template_without_claiming_model_success(self):
        with patch.dict('os.environ', {'AEROTOWER_DISABLE_LLM': '0'}), patch(
            'backend.services.intelligence.language.model_available', return_value=True
        ), patch('backend.services.intelligence.language._generate', side_effect=MemoryError('内存不足')):
            result = parse_description('北京基地，48班航班', use_model=True)
        self.assertEqual(result['method'], 'template-fallback')
        self.assertEqual(result['fields']['flight_count'], 48)
        self.assertEqual(result['model_fields'], {})
        self.assertEqual(result['model_error'], '内存不足')

    def test_retry_patch_preserves_values_already_extracted_by_model(self):
        responses = ['{"基地":"北京","客流变化":"减少20%"}', '{"天气":"大雾","航班数":"48班"}']
        with patch.dict('os.environ', {'AEROTOWER_DISABLE_LLM': '0'}), patch(
            'backend.services.intelligence.language.model_available', return_value=True
        ), patch('backend.services.intelligence.language._generate', side_effect=responses):
            result = parse_description('北京基地，客流减少20%，大雾，48班航班', use_model=True)
        self.assertEqual(result['method'], 'local-qwen')
        self.assertEqual(result['model_fields']['demand_factor'], 0.8)
        self.assertEqual(result['model_field_sources']['demand_factor'], 'initial')
        self.assertEqual(result['model_field_sources']['flight_count'], 'retry')

    def test_missing_values_are_not_filled_into_model_success(self):
        responses = ['{"基地":"北京"}', '{"基地":"北京"}']
        with patch.dict('os.environ', {'AEROTOWER_DISABLE_LLM': '0'}), patch(
            'backend.services.intelligence.language.model_available', return_value=True
        ), patch('backend.services.intelligence.language._generate', side_effect=responses):
            result = parse_description('北京基地，48班航班', use_model=True)
        self.assertNotIn('flight_count', result['model_fields'])
        self.assertEqual(result['method'], 'template-fallback')
        self.assertEqual(result['fields']['flight_count'], 48)

    def test_chinese_normalization_uses_only_model_values_and_keeps_zero(self):
        values = decoded_fields('{"基地":"成都基地","天气":"加一场雷暴","客流变化":"涨两成","备用飞机":"0架","航班数":""}')
        self.assertEqual(values, {'base_airport': '成都', 'weather': 'storm', 'demand_factor': 1.2, 'backup_aircraft': 0})
        self.assertNotIn('flight_count', values)
        self.assertEqual(decoded_fields('{"前序延误":"30分钟"}'), {'previous_delay': 30})

    def test_invalid_json_can_be_repaired_without_providing_answers(self):
        with patch.dict('os.environ', {'AEROTOWER_DISABLE_LLM': '0'}), patch(
            'backend.services.intelligence.language.model_available', return_value=True
        ), patch('backend.services.intelligence.language._generate', side_effect=['不合法JSON', '{"base_airport":"成都"}']) as generate:
            result = parse_description('成都基地', use_model=True)
        self.assertTrue(generate.call_args_list[1].args[2]['invalid_json'])
        self.assertEqual(result['method'], 'local-qwen')
        self.assertEqual(result['initial_model_output'], '不合法JSON')

    def test_retry_receives_field_names_but_not_expected_values(self):
        responses = ['{"base_airport":"北京"}', '{"base_airport":"北京","flight_count":48}']
        with patch.dict('os.environ', {'AEROTOWER_DISABLE_LLM': '0'}), patch(
            'backend.services.intelligence.language.model_available', return_value=True
        ), patch('backend.services.intelligence.language._generate', side_effect=responses) as generate:
            result = parse_description('北京基地，48班航班', use_model=True)
        feedback = generate.call_args_list[1].args[2]
        self.assertEqual(feedback['missing'], ['flight_count'])
        self.assertNotIn('48', json.dumps(feedback))
        self.assertEqual(result['method'], 'local-qwen')
        self.assertTrue(result['retry_used'])

    def test_incorrect_model_is_explicitly_marked_as_template_fallback(self):
        response = '{"base_airport":"北京","flight_count":99}'
        with patch.dict('os.environ', {'AEROTOWER_DISABLE_LLM': '0'}), patch(
            'backend.services.intelligence.language.model_available', return_value=True
        ), patch('backend.services.intelligence.language._generate', return_value=response):
            result = parse_description('北京基地，48班航班', use_model=True)
        self.assertEqual(result['method'], 'template-fallback')
        self.assertEqual(result['fields']['flight_count'], 48)
        self.assertEqual(result['model_fields']['flight_count'], 99)
        self.assertTrue(any('回退' in warning for warning in result['warnings']))

    def test_bool_cannot_be_normalized_to_runway_count_one(self):
        self.assertEqual(decoded_fields('{"capacity":true}'), {})

    def test_ambiguous_or_negated_events_require_manual_choice(self):
        fields, _, warnings = grounded_fields('成都基地，飞机故障，机场关闭60分钟')
        self.assertNotIn('event_type', fields)
        self.assertTrue(warnings)
        self.assertNotIn('event_type', grounded_fields('成都基地，没有飞机故障')[0])

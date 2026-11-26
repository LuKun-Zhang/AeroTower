"""指标聚合口径。"""

import unittest
from types import SimpleNamespace

from backend.services.experiment import metrics


def flight(pax=100):
    return SimpleNamespace(_is_ferry=False, _pax_count=pax)


class MetricsTest(unittest.TestCase):
    def test_aggregate(self):
        gen = {'flights': [flight(), flight(), flight(), flight()]}
        schedule = {
            'aircraft_stats': {'avg_utilization': 50.0},
            'runway': {'stats': {'avg_delay': 1.2}},
            'gates': [{'stats': {'used_gates': 10, 'avg_utilization': 20.0}}],
            'crew': {'coverage': 90.0, 'violations': 2},
            'warnings': ['w'],
        }
        sim = {
            'ever_cancelled': ['1'],
            'ever_delayed': [('2', 30)],
            'arrived': ['2', '3'],
            'series': [{'t': 0}],
            'step_minutes': 15,
        }
        result = metrics.aggregate(gen, schedule, {'meta': {}}, sim)
        v = result['values']
        self.assertEqual(v['total_flights'], 4)
        self.assertEqual(v['cancelled_count'], 1)
        self.assertEqual(v['delayed_count'], 1)
        self.assertEqual(v['on_time_rate'], 50.0)
        self.assertEqual(v['completion_rate'], 66.7)
        self.assertEqual(v['avg_delay_min'], 30.0)
        self.assertEqual(v['gate_avg_utilization'], 20.0)
        self.assertEqual(v['total_passengers'], 400)
        self.assertEqual(result['warnings'], ['w'])


if __name__ == '__main__':
    unittest.main()

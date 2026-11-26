"""实验条件校验与客流解析。"""

import unittest

from backend.services.experiment import conditions
from backend.models.experiment import ExperimentError


def base(**kw):
    data = {
        'name': 't', 'dates': ['2020-11-30'], 'bases': ['成都'], 'seed': 1,
    }
    data.update(kw)
    return data


class ConditionsTest(unittest.TestCase):
    def test_defaults(self):
        cond = conditions.normalize(base())
        self.assertEqual(cond['dates'], ['2020-11-30'])
        self.assertEqual(cond['bases'], ['成都'])
        self.assertEqual(cond['hub'], '成都')
        self.assertEqual(sum(cond['fleet']['mix'].values()), cond['fleet']['size'])
        self.assertEqual(cond['algorithms']['routing'], 'chain_coverage')
        self.assertTrue(cond['traffic']['city_traffic'])

    def test_bad_date(self):
        with self.assertRaises(ExperimentError) as ctx:
            conditions.normalize(base(dates=['2020-12-31']))
        self.assertEqual(ctx.exception.field, 'dates')

    def test_fleet_mix_mismatch(self):
        with self.assertRaises(ExperimentError) as ctx:
            conditions.normalize(base(fleet={'size': 100, 'mix': {'A319': 1, 'A320': 1, 'A321': 1}}))
        self.assertEqual(ctx.exception.field, 'fleet.mix')

    def test_custom_traffic(self):
        cond = conditions.normalize(base(traffic={
            'template': 'custom',
            'pasted': [
                {'origin': '成都', 'destination': '北京', 'daily_pax': 100},
                {'origin': '北京', 'destination': '成都', 'daily_pax': 90},
            ],
        }))
        self.assertEqual(cond['traffic']['template'], 'custom')
        self.assertEqual(len(cond['traffic']['city_traffic']), 2)

    def test_normalized_roundtrip_keeps_custom_traffic(self):
        cond = conditions.normalize(base(traffic={
            'template': 'custom',
            'pasted': [{'origin': '成都', 'destination': '北京', 'daily_pax': 100}],
        }))
        again = conditions.normalize(cond)
        self.assertEqual(again['traffic']['template'], 'custom')
        self.assertEqual(len(again['traffic']['city_traffic']), 1)

    def test_bad_algorithm(self):
        with self.assertRaises(ExperimentError):
            conditions.normalize(base(algorithms={'gate': 'cp_sat'}))


if __name__ == '__main__':
    unittest.main()

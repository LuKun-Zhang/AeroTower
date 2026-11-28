"""实验存储：创建、列表、读取、删除。"""

import shutil
import unittest

from backend.services.experiment import store, conditions

USER = '__tester__'


class StoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(store.user_dir(USER), ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(store.user_dir(USER), ignore_errors=True)

    def test_roundtrip(self):
        cond = conditions.normalize({
            'name': 'store', 'dates': ['2020-11-30'], 'bases': ['成都'], 'seed': 5,
        })
        record = store.create(USER, cond, name='store')
        self.assertTrue(store.load(USER, record.id))
        rows = store.list_for(USER)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, record.id)
        self.assertGreater(store.disk_usage(USER, record.id), 0)
        store.delete(USER, record.id)
        self.assertEqual(store.list_for(USER), [])

    def test_bad_id(self):
        with self.assertRaises(ValueError):
            store.load(USER, '../evil')


if __name__ == '__main__':
    unittest.main()

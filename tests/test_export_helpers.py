import unittest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import export

class TestExportHelpers(unittest.TestCase):
    def test_month_ok(self):
        self.assertTrue(export.month_ok('2023-01-01', '2023-01', '2023-12'))
        self.assertFalse(export.month_ok('2022-12-01', '2023-01', '2023-12'))
        self.assertTrue(export.month_ok(None, '2023-01', '2023-12'))

    def test_fix_user_links(self):
        js = {'subject': '<lj user="bob">', 'body': '<lj user="alice">'}
        export.fix_user_links(js)
        self.assertEqual(js['subject'], 'bob')
        self.assertEqual(js['body'], 'alice')

    def test_get_slug(self):
        js = {'subject': 'Hello World!', 'id': '123'}
        slug = export.get_slug(js)
        self.assertTrue(slug.startswith('Hello-World'))

    def test_json_to_html(self):
        js = {'subject': 'Test', 'body': 'Body', 'date': '2023-01-01'}
        html = export.json_to_html(js)
        self.assertIn('<h1>Test</h1>', html)
        self.assertIn('Body', html)

if __name__ == '__main__':
    unittest.main()

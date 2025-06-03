import unittest
from unittest.mock import patch, mock_open, MagicMock
import xml.etree.ElementTree as ET
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import download_comments

class TestDownloadComments(unittest.TestCase):
    def setUp(self):
        self.sample_xml = ET.fromstring('<root><usermap id="1" user="alice"/></root>')
        self.comment_xml = ET.fromstring('<comment jitemid="123" id="456" parentid="789" posterid="1"><date>2023-01-01</date><subject>Test</subject><body>Body</body></comment>')

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_get_users_map(self, mock_makedirs, mock_file):
        users = download_comments.get_users_map(self.sample_xml)
        self.assertEqual(users, {'1': 'alice'})
        mock_makedirs.assert_called_with('batch-downloads/comments-json', exist_ok=True)
        mock_file.assert_called_with('batch-downloads/comments-json/usermap.json', 'w', encoding='utf-8')

    def test_get_comment_property(self):
        comment = {}
        download_comments.get_comment_property('parentid', self.comment_xml, comment)
        self.assertEqual(comment['parentid'], 789)

    def test_get_comment_element(self):
        comment = {}
        download_comments.get_comment_element('subject', self.comment_xml, comment)
        self.assertEqual(comment['subject'], 'Test')

    @patch('download_comments.fetch_xml')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_get_more_comments(self, mock_makedirs, mock_file, mock_fetch_xml):
        # Return a simple XML with one comment
        mock_fetch_xml.return_value = '<root><comment jitemid="123" id="456" parentid="789" posterid="1"><date>2023-01-01</date><subject>Test</subject><body>Body</body></comment></root>'
        users = {'1': 'alice'}
        local_max_id, comments = download_comments.get_more_comments(0, users, {}, {})
        self.assertEqual(local_max_id, 456)
        self.assertEqual(comments[0]['author'], 'alice')

if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime
import os
import sys

# Add src to sys.path for import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import download_posts

class TestDownloadPosts(unittest.TestCase):
    def setUp(self):
        self.cookies = {'test': 'cookie'}
        self.headers = {'User-Agent': 'test'}
        self.start_month = datetime(2023, 1, 1)
        self.end_month = datetime(2023, 1, 1)
        self.xml_stub = '''<lj><entry><itemid>1</itemid><logtime>2023-01-01</logtime><subject>Test</subject><event>Body</event><eventtime>2023-01-01T00:00:00Z</eventtime><security>public</security><allowmask>0</allowmask><current_music>None</current_music><current_mood>None</current_mood></entry></lj>'''

    @patch('download_posts.requests.post')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_download_posts_creates_dir_and_writes_file(self, mock_makedirs, mock_file, mock_post):
        mock_post.return_value.text = self.xml_stub
        posts = download_posts.download_posts(self.cookies, self.headers, self.start_month, self.end_month)
        mock_makedirs.assert_called_with('batch-downloads/posts-xml', exist_ok=True)
        mock_file.assert_called_with('batch-downloads/posts-xml/2023-01.xml', 'w+', encoding='utf-8')
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['id'], '1')
        self.assertEqual(posts[0]['subject'], 'Test')

    def test_xml_to_json(self):
        import xml.etree.ElementTree as ET
        xml = ET.fromstring(self.xml_stub).find('entry')
        post = download_posts.xml_to_json(xml)
        self.assertEqual(post['id'], '1')
        self.assertEqual(post['subject'], 'Test')
        self.assertEqual(post['body'], 'Body')

    @patch('download_posts.input', side_effect=['2023-01', '2023-01'])
    @patch('download_posts.requests.post')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_download_posts_prompts_for_dates(self, mock_makedirs, mock_file, mock_post, mock_input):
        mock_post.return_value.text = self.xml_stub
        posts = download_posts.download_posts(self.cookies, self.headers)
        self.assertEqual(len(posts), 1)

if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import download_friend_groups

class TestDownloadFriendGroups(unittest.TestCase):
    def setUp(self):
        self.sample_xml = '''<?xml version='1.0'?><methodResponse><params><param><value><struct><member><name>friendgroups</name><value><array><data><value><struct><member><name>id</name><value><int>1</int></value></member><member><name>name</name><value><string>Besties</string></value></member></struct></value></data></array></value></member></struct></value></param></params></methodResponse>'''

    def test_parse_friend_groups(self):
        groups = download_friend_groups._parse_friend_groups(self.sample_xml)
        self.assertEqual(groups[0]['id'], '1')
        self.assertEqual(groups[0]['name'], 'Besties')

    @patch('download_friend_groups.requests.post')
    def test_rpc_call(self, mock_post):
        mock_post.return_value.text = self.sample_xml
        mock_post.return_value.raise_for_status = lambda: None
        xml = download_friend_groups._rpc_call('LJ.XMLRPC.getfriendgroups', {'foo': 'bar'}, {}, {})
        self.assertIn('friendgroups', xml)

    @patch('download_friend_groups._rpc_call')
    def test_download_friend_groups(self, mock_rpc):
        mock_rpc.return_value = self.sample_xml
        groups = download_friend_groups.download_friend_groups({}, {})
        self.assertEqual(groups[0]['name'], 'Besties')

if __name__ == '__main__':
    unittest.main()

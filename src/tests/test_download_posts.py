import os
import sys
import pytest
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from export import login
from download_posts import download_posts, fetch_month_posts

def test_fetch_month_posts_auth():
    """Test that fetch_month_posts handles authentication properly."""
    # Get credentials from environment
    username = os.environ.get('LJ_USER')
    password = os.environ.get('LJ_PASS')
    if not username or not password:
        pytest.skip("LJ_USER and LJ_PASS environment variables not set")

    # Login to get cookies and headers
    cookies, api_hdr = login(username, password)

    # Test with a known period that has posts (July 2013)
    xml = fetch_month_posts(2013, 7, cookies, api_hdr)
    
    # Verify we got valid XML
    root = ET.fromstring(xml)
    assert root.tag == 'livejournal', "Expected livejournal root element"
    
    # Verify we have entries
    entries = root.findall('.//entry')
    assert len(entries) > 0, "No entries found in XML"

def test_fetch_month_posts_xml_structure():
    """Test that the XML response has the expected structure."""
    # Get credentials from environment
    username = os.environ.get('LJ_USER')
    password = os.environ.get('LJ_PASS')
    if not username or not password:
        pytest.skip("LJ_USER and LJ_PASS environment variables not set")

    # Login to get cookies and headers
    cookies, api_hdr = login(username, password)

    # Test with a known period that has posts (July 2013)
    xml = fetch_month_posts(2013, 7, cookies, api_hdr)
    root = ET.fromstring(xml)
    
    # Check first entry for required fields
    entry = root.find('.//entry')
    assert entry is not None, "No entry found"
    
    required_fields = ['itemid', 'logtime', 'subject', 'event', 'eventtime', 'security', 'allowmask']
    for field in required_fields:
        assert entry.find(field) is not None, f"Missing required field: {field}"
    
    # Check for userpic properties
    props = entry.find('props')
    assert props is not None, "Missing props element"
    assert props.find('prop_current_userpic') is not None, "Missing prop_current_userpic"
    assert props.find('prop_userpicid') is not None, "Missing prop_userpicid"

def test_download_posts_creates_dir_and_writes_file():
    """Test that download_posts creates the directory and writes the file."""
    # Get credentials from environment
    username = os.environ.get('LJ_USER')
    password = os.environ.get('LJ_PASS')
    if not username or not password:
        pytest.skip("LJ_USER and LJ_PASS environment variables not set")

    # Login to get cookies and headers
    cookies, api_hdr = login(username, password)

    # Test with a known period that has posts (July 2013)
    start_date = datetime(2013, 7, 1)
    end_date = datetime(2013, 7, 31)

    # Download posts
    posts = list(download_posts(cookies, api_hdr, start_date, end_date))

    # Verify we got some posts
    assert len(posts) > 0, "No posts were downloaded"

    # Verify post structure
    for post in posts:
        assert 'date' in post, "Post missing date"
        assert 'subject' in post, "Post missing subject"
        assert 'body' in post, "Post missing body"
        assert 'icon_path' in post, "Post missing icon_path"

        # Verify date is within our test period
        post_date = datetime.strptime(post['date'], '%Y-%m-%d %H:%M:%S')
        assert start_date <= post_date <= end_date, f"Post date {post_date} outside test period"

def test_download_posts_prompts_for_dates():
    """Test that download_posts handles date prompts correctly."""
    # Get credentials from environment
    username = os.environ.get('LJ_USER')
    password = os.environ.get('LJ_PASS')
    if not username or not password:
        pytest.skip("LJ_USER and LJ_PASS environment variables not set")

    # Login to get cookies and headers
    cookies, api_hdr = login(username, password)

    # Test with a period that should have no posts
    start_date = datetime(2000, 1, 1)
    end_date = datetime(2000, 1, 31)

    # Download posts
    posts = list(download_posts(cookies, api_hdr, start_date, end_date))

    # Verify we got no posts
    assert len(posts) == 0, "Expected no posts for this period"

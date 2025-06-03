import os
import sys
import pytest
from datetime import datetime
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from export import login
from download_posts import download_posts

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
        assert 'tags' in post, "Post missing tags"
        assert 'comments' in post, "Post missing comments"

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

#!/usr/bin/python3

# NOTE: This script is now located in src/ and is intended to be run as a module or via Docker.
# All code is commented for clarity for junior developers.

import json
import os
import requests
from sys import exit as sysexit
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import sys
import time

# Move DATE_FORMAT to module level
DATE_FORMAT = '%Y-%m'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logger import setup_logger
from download_comments import UserpicManager, fetch_xml

logger = setup_logger(__name__)

def fetch_month_posts(year, month, cookies, headers):
    logger.debug(f"Fetching posts for {year}-{month:02d}")
    response = requests.post(
        'https://www.livejournal.com/export_do.bml',
        headers=headers,
        cookies=cookies,
        data={
            'what': 'journal',
            'year': year,
            'month': '{0:02d}'.format(month),
            'format': 'xml',
            'header': 'on',
            'encid': '2',
            'field_itemid': 'on',
            'field_eventtime': 'on',
            'field_logtime': 'on',
            'field_subject': 'on',
            'field_event': 'on',
            'field_security': 'on',
            'field_allowmask': 'on',
            'field_currents': 'on'
        }
    )
    if response.status_code != 200:
        logger.error(f"Failed to fetch posts for {year}-{month:02d}: HTTP {response.status_code}")
        raise RuntimeError(f"HTTP {response.status_code}")
    logger.debug(f"Successfully fetched posts for {year}-{month:02d}")
    return response.text

def xml_to_json(xml):
    def f(field):
        return xml.find(field).text

    return {
        'id': f('itemid'),
        'date': f('logtime'),
        'subject': f('subject') or '',
        'body': f('event'),
        'eventtime': f('eventtime'),
        'security': f('security'),
        'allowmask': f('allowmask'),
        'current_music': f('current_music'),
        'current_mood': f('current_mood')
    }

def download_posts(cookies, headers, start_date=None, end_date=None):
    """Download posts from LiveJournal API."""
    logger.info("Starting post download process...")
    os.makedirs('batch-downloads/posts-xml', exist_ok=True)
    os.makedirs('batch-downloads/posts-json', exist_ok=True)
    os.makedirs('images/icons', exist_ok=True)

    # Create userpic manager
    userpic_mgr = UserpicManager(cookies, headers)

    # Initialize list to store all posts
    all_posts = []
    
    # Iterate through each month in the range
    current_date = start_date
    while current_date <= end_date:
        logger.debug(f"Fetching posts for {current_date.year}-{current_date.month:02d}")
        
        # Get post metadata for this month
        metadata_xml = fetch_month_posts(current_date.year, current_date.month, cookies, headers)
        xml_path = f'batch-downloads/posts-xml/post_meta_{current_date.year}_{current_date.month:02d}.xml'
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(metadata_xml)
        logger.debug(f"Saved post metadata XML to {xml_path}")

        metadata = ET.fromstring(metadata_xml)
        
        # Process each post in the XML
        for post_xml in metadata.findall('.//entry'):
            post = xml_to_json(post_xml)
            
            # Process userpics for post authors
            posterid = post.get('posterid')
            if posterid:
                # Get the userpic URL (from cache if available)
                url = userpic_mgr.get_userpic_url(posterid, "post", post['id'])
                if url:
                    # Download the userpic if needed
                    icon_path = userpic_mgr.download_userpic(posterid, url)
                    post["icon_path"] = icon_path
                else:
                    post["icon_path"] = None

            # Save post to JSON
            post_id = post['id']
            with open(f'batch-downloads/posts-json/{post_id}.json', 'w', encoding='utf-8') as f:
                json.dump(post, f, ensure_ascii=False, indent=2)
            all_posts.append(post)

        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
        
        # Avoid overwhelming the server
        time.sleep(0.5)  # Brief pause between months

    logger.info(f"Processed {len(all_posts)} total posts")
    
    # Print final cache stats
    stats = userpic_mgr.get_stats()
    logger.info(f"Final userpic cache stats: {stats['cache_size']} users cached, {stats['hit_rate']} hit rate, {stats['downloaded']} icons downloaded")

    return all_posts

if __name__ == '__main__':
    download_posts(None, None)

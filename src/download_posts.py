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
import re
from urllib.parse import urlparse, unquote

DATE_FORMAT = '%Y-%m'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fetch_month_posts(year, month, cookies, headers):
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

def fetch_comments(post_id, cookies, headers):
    response = requests.get(
        f'https://www.livejournal.com/export_comments.bml?get=comment_body&id={post_id}',
        headers=headers,
        cookies=cookies
    )
    return response.text

def extract_lj_usernames(text):
    """Extract LiveJournal usernames from text using <lj user=username> tags."""
    if not text:
        return set()
    usernames = set()
    # Find all <lj user=username> tags
    lj_user_pattern = r'<lj\s+user=([^>]+)>'
    matches = re.findall(lj_user_pattern, text)
    # Clean up usernames (remove quotes and whitespace)
    usernames.update(match.strip('"\' ') for match in matches)
    return usernames

def comments_xml_to_json(xml):
    """Convert comments XML to JSON format, handling deleted comments."""
    root = ET.fromstring(xml)
    comments = []
    user_map = {}  # Map of userid -> username
    
    for comment in root.findall('.//comment'):
        comment_data = {
            'id': comment.get('id'),
            'jitemid': comment.get('jitemid'),
            'posterid': comment.get('posterid'),
            'parentid': comment.get('parentid'),
            'date': comment.find('date').text if comment.find('date') is not None else None,
            'deleted': False
        }
        
        # Check for username in the comment
        username = comment.get('user')
        if username:
            user_map[comment.get('posterid')] = username.strip('"\' ')
        
        # Handle subject if present
        subject = comment.find('subject')
        if subject is not None and subject.text:
            comment_data['subject'] = subject.text
        
        # Handle body
        body_element = comment.find('body')
        if body_element is not None and body_element.text:
            comment_data['body'] = body_element.text
            # Extract usernames from body text
            usernames = extract_lj_usernames(body_element.text)
            for username in usernames:
                if comment.get('posterid'):
                    user_map[comment.get('posterid')] = username
        else:
            comment_data['deleted'] = True
            comment_data['body'] = None
        
        comments.append(comment_data)
    
    return comments, user_map

def fetch_user_info(username, cookies, headers):
    """Fetch user information using the LiveJournal API."""
    # Clean up username
    username = username.strip('"\' ')
    
    # Try to get user info directly
    response = requests.get(
        'https://www.livejournal.com/export_do.bml',
        params={
            'type': 'user',
            'what': 'user',
            'user': username
        },
        headers=headers,
        cookies=cookies
    )
    
    if response.status_code == 200 and response.text:
        try:
            root = ET.fromstring(response.text)
            user = root.find('.//user')
            if user is not None:
                return response.text
        except Exception as e:
            print(f"Error parsing user info for username {username}: {str(e)}")
    
    return None

def xml_to_user_json(xml):
    """Convert user XML to JSON format."""
    root = ET.fromstring(xml)
    user = root.find('.//user')
    if user is None:
        return None
    
    return {
        'username': user.find('username').text if user.find('username') is not None else None,
        'userid': user.find('userid').text if user.find('userid') is not None else None,
        'fullname': user.find('fullname').text if user.find('fullname') is not None else None,
        'url': user.find('url').text if user.find('url') is not None else None,
        'journaltype': user.find('journaltype').text if user.find('journaltype') is not None else None,
        'last_updated': user.find('last_updated').text if user.find('last_updated') is not None else None
    }

def save_user_info(user_json, userid):
    """Save user information to a JSON file."""
    user_dir = f'users/{userid}'
    os.makedirs(user_dir, exist_ok=True)
    
    # If no user info was found, save a minimal record
    if not user_json:
        user_json = {
            "profile_unavailable": True,
            "last_checked": datetime.now().isoformat()
        }
    
    with open(f'{user_dir}/user.json', 'w+', encoding='utf-8') as file:
        json.dump(user_json, file, indent=4)

def collect_user_ids(post_json, comments_json):
    """Collect all user IDs from a post and its comments."""
    user_ids = set()
    
    # Add post author
    if 'author' in post_json:
        user_ids.add(post_json['author'])
    
    # Add comment authors
    if comments_json:
        for comment in comments_json:
            if 'posterid' in comment:
                user_ids.add(comment['posterid'])
    
    return user_ids

def save_user_mapping(user_map):
    """Save the user ID to username mapping to a JSON file."""
    if not user_map:
        return
    
    os.makedirs('users', exist_ok=True)
    with open('users/user_map.json', 'w+', encoding='utf-8') as file:
        json.dump(user_map, file, indent=4)

def download_posts(cookies, headers, start_month=None, end_month=None):
    # Create necessary directories
    os.makedirs('batch-downloads/posts-xml', exist_ok=True)
    os.makedirs('batch-downloads/comments-xml', exist_ok=True)
    os.makedirs('users', exist_ok=True)

    # Use passed-in start/end months if provided (from export.py), else prompt
    if start_month is None or end_month is None:
        try:
            start_month = datetime.strptime(input("Enter start month in YYYY-MM format: "), DATE_FORMAT)
        except Exception as e:
            print(f"\nError with start month entered. Error: {e}. Exiting...")
            sysexit(1)
        try:
            end_month = datetime.strptime(input("Enter end month in YYYY-MM format: "), DATE_FORMAT)
        except Exception as e:
            print(f"\nError with end month entered. Error: {e}. Exiting...")
            sysexit(1)

    xml_posts = []
    month_cursor = start_month
    all_user_ids = set()
    user_map = {}  # Global user mapping

    while month_cursor <= end_month:
        year = month_cursor.year
        month = month_cursor.month

        xml = fetch_month_posts(year, month, cookies, headers)
        xml_posts.extend(list(ET.fromstring(xml).iter('entry')))

        with open(f'batch-downloads/posts-xml/{year}-{month:02d}.xml', 'w+', encoding='utf-8') as file:
            file.write(xml)
        
        month_cursor = month_cursor + relativedelta(months=1)

    json_posts = list(map(xml_to_json, xml_posts))

    # Process each post and its comments
    for post in xml_posts:
        post_json = xml_to_json(post)
        post_date = datetime.strptime(post_json['date'], '%Y-%m-%d %H:%M:%S')
        post_dir = f'posts/{post_date.year}/{post_date.month:02d}/{post_date.year}-{post_date.month:02d}-{post_date.day:02d}-{post_date.hour:02d}-{post_date.minute:02d}-{post_date.second:02d}-{post_json["id"]}'
        os.makedirs(post_dir, exist_ok=True)
        
        # Save post JSON
        with open(f'{post_dir}/post.json', 'w+', encoding='utf-8') as file:
            json.dump(post_json, file, indent=4)
        
        # Fetch and save comments for this post
        comments = fetch_comments(post_json['id'], cookies, headers)
        comments_json = None
        if comments:
            # Save XML comments
            with open(f'batch-downloads/comments-xml/comments_{post_json["id"]}.xml', 'w+', encoding='utf-8') as file:
                file.write(comments)
            
            # Convert to JSON and save alongside post
            comments_json, post_user_map = comments_xml_to_json(comments)
            user_map.update(post_user_map)  # Update global user mapping
            comments_path = f'{post_dir}/comments.json'
            with open(comments_path, 'w+', encoding='utf-8') as file:
                json.dump(comments_json, file, indent=4)
        
        # Collect user IDs from post and comments
        user_ids = collect_user_ids(post_json, comments_json)
        all_user_ids.update(user_ids)
        
        # Download images
        if 'event' in post_json:
            image_urls = extract_image_urls(post_json['event'])
            for url in image_urls:
                download_image(url, post_dir, cookies, headers)
                time.sleep(1)  # Rate limiting

    # Save the user mapping
    save_user_mapping(user_map)

    # Fetch and save user information for all collected user IDs
    for userid in all_user_ids:
        try:
            # If we have a username for this userid, use it
            username = user_map.get(str(userid))
            if username:
                user_xml = fetch_user_info(username, cookies, headers)
                user_json = xml_to_user_json(user_xml) if user_xml else None
                save_user_info(user_json, userid)
                time.sleep(1)  # Rate limiting
        except Exception as e:
            print(f"Error fetching user info for userid {userid}: {str(e)}")
            # Save minimal info for failed fetches
            save_user_info(None, userid)

    return json_posts

def get_comments(username, password, itemid):
    url = "https://www.livejournal.com/interface/xmlrpc"
    headers = {'Content-Type': 'application/xml'}
    
    # Construct the XML-RPC request
    xml_body = f"""
    <methodCall>
      <methodName>LJ.XMLRPC.getcomments</methodName>
      <params>
        <param>
          <value>
            <struct>
              <member>
                <name>username</name>
                <value><string>{username}</string></value>
              </member>
              <member>
                <name>password</name>
                <value><string>{password}</string></value>
              </member>
              <member>
                <name>itemid</name>
                <value><int>{itemid}</int></value>
              </member>
            </struct>
          </value>
        </param>
      </params>
    </methodCall>
    """
    
    # Send the request
    response = requests.post(url, headers=headers, data=xml_body)
    
    # Parse the response
    if response.status_code == 200:
        root = ET.fromstring(response.text)
        # Process the comments from the response
        # This will depend on the structure of the response
        return root
    else:
        print(f"Error: {response.status_code}")
        return None

def extract_image_urls(text):
    # Find all img tags
    img_pattern = r'<img[^>]+src="([^"]+)"'
    urls = re.findall(img_pattern, text)
    
    # Also find any direct image URLs
    url_pattern = r'https?://[^\s<>"]+?\.(?:jpg|jpeg|gif|png|bmp|webp)'
    urls.extend(re.findall(url_pattern, text))
    
    return list(set(urls))  # Remove duplicates

def download_image(url, post_dir, cookies, headers):
    try:
        # Parse the URL to get the filename
        parsed_url = urlparse(url)
        filename = os.path.basename(unquote(parsed_url.path))
        
        # Create images directory if it doesn't exist
        images_dir = os.path.join(post_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        # Download the image
        response = requests.get(url, cookies=cookies, headers=headers)
        if response.status_code == 200:
            image_path = os.path.join(images_dir, filename)
            with open(image_path, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded image: {filename}")
        else:
            print(f"Failed to download image {url}: {response.status_code}")
    except Exception as e:
        print(f"Error downloading image {url}: {str(e)}")

if __name__ == '__main__':
    download_posts(None, None)

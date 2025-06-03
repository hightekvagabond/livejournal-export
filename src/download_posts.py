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

def comments_xml_to_json(xml):
    root = ET.fromstring(xml)
    comments = []
    for comment in root.findall('.//comment'):
        body_element = comment.find('body')
        if body_element is not None:
            comments.append({
                'id': comment.get('id'),
                'jitemid': comment.get('jitemid'),
                'posterid': comment.get('posterid'),
                'parentid': comment.get('parentid'),
                'body': body_element.text,
                'date': comment.find('date').text
            })
        else:
            print(f"Warning: Comment {comment.get('id')} has no body element.")
    return comments

def download_posts(cookies, headers, start_month=None, end_month=None):
    # Create necessary directories
    os.makedirs('batch-downloads/posts-xml', exist_ok=True)
    os.makedirs('batch-downloads/comments-xml', exist_ok=True)

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
        if comments:
            # Save XML comments
            with open(f'batch-downloads/comments-xml/comments_{post_json["id"]}.xml', 'w+', encoding='utf-8') as file:
                file.write(comments)
            
            # Convert to JSON and save alongside post
            comments_json = comments_xml_to_json(comments)
            comments_path = f'{post_dir}/comments.json'
            with open(comments_path, 'w+', encoding='utf-8') as file:
                json.dump(comments_json, file, indent=4)
        
        # Download images
        if 'event' in post_json:
            image_urls = extract_image_urls(post_json['event'])
            for url in image_urls:
                download_image(url, post_dir, cookies, headers)
                time.sleep(1)  # Rate limiting

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

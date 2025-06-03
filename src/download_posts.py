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

def download_posts(cookies, headers, start_month=None, end_month=None):
    os.makedirs('batch-downloads/posts-xml', exist_ok=True)
    os.makedirs('batch-downloads/comments-xml', exist_ok=True)  # Create directory for comments

    # Use passed-in start/end months if provided (from export.py), else prompt
    if start_month is None or end_month is None:
        DATE_FORMAT = '%Y-%m'
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

    # Fetch comments for post ID 338230
    comments = get_comments("hightekvagabond", "your_password", 338230)
    if comments:
        # Save comments to a file or process them as needed
        with open('batch-downloads/comments-xml/comments_338230.xml', 'w+', encoding='utf-8') as file:
            file.write(ET.tostring(comments, encoding='unicode'))

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

if __name__ == '__main__':
    download_posts(None, None)

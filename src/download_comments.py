#!/usr/bin/python3

# NOTE: This script is now located in src/ and is intended to be run as a module or via Docker.
# All code is commented for clarity for junior developers.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import requests
import xml.etree.ElementTree as ET
from logger import setup_logger
from datetime import datetime
import hashlib
import time
import glob

logger = setup_logger(__name__)

class UserpicManager:
    def __init__(self, cookies, headers):
        self.cookies = cookies
        self.headers = headers
        self.cache = {}  # user_id -> {userpicid -> url}
        self.USERPIC_API = "https://www.livejournal.com/interface/xmlrpc"
        self.download_count = 0
        self.cache_hits = 0
        self.total_requests = 0
        
    def get_userpic_url(self, userid, userpicid=None, source_type=None, source_id=None):
        """Get userpic URL from cache or API, with built-in caching"""
        self.total_requests += 1
        
        # Initialize user's cache if needed
        if userid not in self.cache:
            self.cache[userid] = {}
            
        # Check cache first
        if userpicid and userpicid in self.cache[userid]:
            self.cache_hits += 1
            return self.cache[userid][userpicid]
        
        source_info = f" from {source_type} {source_id}" if source_type and source_id else ""
        logger.debug(f"Fetching userpic URL for user {userid}{source_info}")
        
        # XML-RPC call to get userpics for a user
        payload = {
            "auth_method": "cookie",
            "ver": "1",
            "userid": str(userid),
        }
        
        # Minimal XML-RPC request for userpics.get
        xml_params = "".join(
            f"<param><value><string>{value}</string></value></param>" for value in payload.values()
        )
        body = (
            f"<?xml version='1.0'?>"
            f"<methodCall><methodName>LJ.XMLRPC.userpics.get</methodName><params>{xml_params}</params></methodCall>"
        )
        
        try:
            r = requests.post(self.USERPIC_API, data=body, headers=self.headers, cookies=self.cookies, timeout=30)
            r.raise_for_status()
            
            root = ET.fromstring(r.text)
            
            # Check for fault
            fault = root.find(".//fault")
            if fault is not None:
                fault_string = fault.find(".//string")
                if fault_string is not None:
                    logger.error(f"API returned fault for user {userid}: {fault_string.text}")
                return None
            
            # Process all userpics
            for userpic in root.findall(".//userpic"):
                picid = userpic.find("id")
                url = userpic.find("url")
                if picid is not None and url is not None:
                    self.cache[userid][picid.text] = url.text
            
            # Return specific userpic if requested, otherwise return default
            if userpicid and userpicid in self.cache[userid]:
                return self.cache[userid][userpicid]
            elif self.cache[userid]:
                # Return first userpic as default
                return next(iter(self.cache[userid].values()))
                
            # No userpic found
            logger.debug(f"No userpic found for user {userid}{source_info}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching userpic for user {userid}{source_info}: {e}")
            return None
    
    def download_userpic(self, userid, userpicid, url):
        """Download userpic if needed and return the local path"""
        if not url:
            return None
            
        icon_dir = f"images/icons/{userid}"
        os.makedirs(icon_dir, exist_ok=True)
        ext = os.path.splitext(url)[1] or ".jpg"
        icon_path = f"{icon_dir}/{userpicid}{ext}"
        
        # Skip if already downloaded
        if os.path.exists(icon_path):
            return icon_path
            
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            with open(icon_path, "wb") as icf:
                icf.write(r.content)
            self.download_count += 1
            logger.debug(f"Downloaded icon for user {userid}")
            return icon_path
        except Exception as e:
            logger.error(f"Failed to download icon for user {userid}: {e}")
            return None
    
    def get_stats(self):
        """Return cache statistics"""
        return {
            "cache_size": len(self.cache),
            "cache_hits": self.cache_hits,
            "total_requests": self.total_requests,
            "hit_rate": f"{(self.cache_hits / self.total_requests) * 100:.1f}%" if self.total_requests > 0 else "0%",
            "downloaded": self.download_count
        }

def fetch_xml(params, cookies, headers):
    logger.debug(f"Fetching XML with params: {params}")
    response = requests.get(
        'https://www.livejournal.com/export_comments.bml',
        params=params,
        headers=headers,
        cookies=cookies
    )
    if response.status_code != 200:
        logger.error(f"Failed to fetch XML: HTTP {response.status_code}")
        raise RuntimeError(f"HTTP {response.status_code}")
    return response.text


def get_users_map(xml):
    users = {}
    os.makedirs('batch-downloads/comments-json', exist_ok=True)  # Ensure directory exists
    for user in xml.iter('usermap'):
        users[user.attrib['id']] = user.attrib['user']
    with open('batch-downloads/comments-json/usermap.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(users, ensure_ascii=False, indent=2))
    logger.debug(f"Found {len(users)} users in usermap")
    return users


def get_comment_property(name, comment_xml, comment):
    if name in comment_xml.attrib:
        comment[name] = int(comment_xml.attrib[name])


def get_comment_element(name, comment_xml, comment):
    elements = comment_xml.findall(name)
    if len(elements) > 0:
        comment[name] = elements[0].text


def get_more_comments(start_id, users, cookies, headers):
    comments = []
    local_max_id = -1

    # Ensure the directory exists before writing
    os.makedirs('batch-downloads/comments-xml', exist_ok=True)
    xml = fetch_xml({'get': 'comment_body', 'startid': start_id}, cookies, headers)
    xml_path = f"batch-downloads/comments-xml/comment_body-{start_id}.xml"
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml)
    logger.debug(f"Saved comment XML to {xml_path}")

    for comment_xml in ET.fromstring(xml).iter('comment'):
        comment = {
            'jitemid': int(comment_xml.attrib['jitemid']),
            'id': int(comment_xml.attrib['id']),
            'children': []
        }
        get_comment_property('parentid', comment_xml, comment)
        get_comment_property('posterid', comment_xml, comment)
        get_comment_element('date', comment_xml, comment)
        get_comment_element('subject', comment_xml, comment)
        get_comment_element('body', comment_xml, comment)

        if 'state' in comment_xml.attrib:
            comment['state'] = comment_xml.attrib['state']

        if 'posterid' in comment:
            comment['author'] = users.get(str(comment['posterid']), "deleted-user")

        local_max_id = max(local_max_id, comment['id'])
        comments.append(comment)

    logger.debug(f"Processed {len(comments)} comments from batch starting at ID {start_id}")
    return local_max_id, comments

def get_comments_for_post(post_id, cookies, headers):
    """Get comments for a specific post using ditemid."""
    logger.debug(f"Fetching comments for post {post_id}")
    
    # Convert post_id to ditemid (post_id << 8)
    ditemid = int(post_id) << 8
    logger.debug(f"Using ditemid {ditemid} for post {post_id}")
    
    # XML-RPC call to get comments
    payload = {
        "auth_method": "cookie",
        "ver": "1",
        "ditemid": ditemid,
        "journal": os.environ.get('LJ_USER'),
        "includeposter": "1",
        "expand_meta": "1"
    }
    
    # Construct XML-RPC request
    xml_params = "".join(
        f"<param><value><string>{value}</string></value></param>" for value in payload.values()
    )
    body = (
        f"<?xml version='1.0'?>"
        f"<methodCall><methodName>LJ.XMLRPC.getcomments</methodName><params>{xml_params}</params></methodCall>"
    )
    
    try:
        response = requests.post(
            "https://www.livejournal.com/interface/xmlrpc",
            data=body,
            headers=headers,
            cookies=cookies,
            timeout=30
        )
        response.raise_for_status()
        
        # Log the full response for debugging
        logger.debug(f"API Response for post {post_id}: {response.text}")
        
        root = ET.fromstring(response.text)
        
        # Check for fault
        fault = root.find(".//fault")
        if fault is not None:
            fault_string = fault.find(".//string")
            if fault_string is not None:
                logger.error(f"API returned fault for post {post_id}: {fault_string.text}")
            return []
        
        comments = []
        for comment_xml in root.findall(".//comment"):
            comment = {
                'jitemid': int(comment_xml.attrib['jitemid']),
                'id': int(comment_xml.attrib['id']),
                'children': []
            }
            
            # Get all comment properties
            get_comment_property('parentid', comment_xml, comment)
            get_comment_property('posterid', comment_xml, comment)
            get_comment_property('userpicid', comment_xml, comment)
            get_comment_element('date', comment_xml, comment)
            get_comment_element('subject', comment_xml, comment)
            get_comment_element('body', comment_xml, comment)
            get_comment_element('postername', comment_xml, comment)
            
            if 'state' in comment_xml.attrib:
                comment['state'] = comment_xml.attrib['state']
                
            comments.append(comment)
            
        logger.debug(f"Found {len(comments)} comments for post {post_id}")
        return comments
        
    except Exception as e:
        logger.error(f"Error fetching comments for post {post_id}: {e}")
        return []

def download_comments(cookies, headers):
    logger.info("Starting comment download process...")
    os.makedirs('batch-downloads/comments-xml', exist_ok=True)
    os.makedirs('batch-downloads/comments-json', exist_ok=True)
    os.makedirs('images/icons', exist_ok=True)

    # Create userpic manager
    userpic_mgr = UserpicManager(cookies, headers)

    # Get list of posts we have
    post_files = glob.glob('batch-downloads/posts-json/*.json')
    logger.info(f"Found {len(post_files)} posts to process comments for")
    
    all_comments = []
    for post_file in post_files:
        post_id = os.path.splitext(os.path.basename(post_file))[0]
        
        # Get comments for this post
        comments = get_comments_for_post(post_id, cookies, headers)
        
        # Process userpics for comments
        for comment in comments:
            posterid = comment.get('posterid')
            if posterid:
                # Get the userpic URL (from cache if available)
                url = userpic_mgr.get_userpic_url(posterid, comment.get('userpicid'), "comment", f"post {post_id} comment {comment['id']}")
                if url:
                    # Download the userpic if needed
                    icon_path = userpic_mgr.download_userpic(posterid, comment.get('userpicid'), url)
                    comment["icon_path"] = icon_path
                else:
                    comment["icon_path"] = None
        
        # Save comments to post-specific directory if there are any
        if comments:
            # Find the post directory
            post_dirs = glob.glob(f'posts/*/*/*-{post_id}')
            if post_dirs:
                post_dir = post_dirs[0]
                comments_path = os.path.join(post_dir, 'comments.json')
                with open(comments_path, 'w', encoding='utf-8') as f:
                    json.dump(comments, f, ensure_ascii=False, indent=2)
                logger.debug(f"Saved {len(comments)} comments to {comments_path}")
        
        all_comments.extend(comments)
        logger.debug(f"Processed comments for post {post_id}")
        
        # Avoid overwhelming the server
        time.sleep(0.5)  # Brief pause between posts

    logger.info(f"Processed {len(all_comments)} total comments")

    with open('batch-downloads/comments-json/all.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(all_comments, ensure_ascii=False, indent=2))
    logger.info(f"Saved {len(all_comments)} comments to JSON")
    
    # Print final cache stats
    stats = userpic_mgr.get_stats()
    logger.info(f"Final userpic cache stats: {stats['cache_size']} users cached, {stats['hit_rate']} hit rate, {stats['downloaded']} icons downloaded")

    return all_comments


if __name__ == '__main__':
    download_comments()

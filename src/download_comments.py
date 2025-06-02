#!/usr/bin/python3

# NOTE: This script is now located in src/ and is intended to be run as a module or via Docker.
# All code is commented for clarity for junior developers.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import requests
import xml.etree.ElementTree as ET

def fetch_xml(params, cookies, headers):
    response = requests.get(
        'https://www.livejournal.com/export_comments.bml',
        params=params,
        headers=headers,
        cookies=cookies
    )

    return response.text


def get_users_map(xml):
    users = {}
    os.makedirs('batch-downloads/comments-json', exist_ok=True)  # Ensure directory exists
    for user in xml.iter('usermap'):
        users[user.attrib['id']] = user.attrib['user']
    with open('batch-downloads/comments-json/usermap.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(users, ensure_ascii=False, indent=2))

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

    xml = fetch_xml({'get': 'comment_body', 'startid': start_id}, cookies, headers)
    with open('comments-xml/comment_body-{0}.xml'.format(start_id), 'w', encoding='utf-8') as f:
        f.write(xml)

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

    return local_max_id, comments

# --- Userpic (icon) download logic ---
USERPIC_API = "https://www.livejournal.com/interface/xmlrpc"
import hashlib

def get_userpic_url(userid, cookies, headers):
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
        f"<methodCall><methodName>LJ.XMLRPC.getuserpics</methodName><params>{xml_params}</params></methodCall>"
    )
    r = requests.post(USERPIC_API, data=body, headers=headers, cookies=cookies, timeout=30)
    r.raise_for_status()
    import xml.etree.ElementTree as ET
    root = ET.fromstring(r.text)
    # Find the first userpic URL (default)
    url_elem = root.find(".//member[name='url']/value/string")
    if url_elem is not None:
        return url_elem.text
    return None


def download_comments(cookies, headers):
    os.makedirs('batch-downloads/comments-xml', exist_ok=True)
    os.makedirs('batch-downloads/comments-json', exist_ok=True)
    os.makedirs('images/icons', exist_ok=True)

    metadata_xml = fetch_xml({'get': 'comment_meta', 'startid': 0}, cookies, headers)
    with open('batch-downloads/comments-xml/comment_meta.xml', 'w', encoding='utf-8') as f:
        f.write(metadata_xml)

    metadata = ET.fromstring(metadata_xml)
    users = get_users_map(metadata)

    all_comments = []
    start_id = 0
    max_id = int(metadata.find('maxid').text)
    userpic_cache = {}
    while start_id < max_id:
        start_id, comments = get_more_comments(start_id + 1, users, cookies, headers)
        for comment in comments:
            posterid = comment.get('posterid')
            if posterid:
                if posterid not in userpic_cache:
                    url = get_userpic_url(posterid, cookies, headers)
                    userpic_cache[posterid] = url
                    if url:
                        icon_dir = f"images/icons/{posterid}"
                        os.makedirs(icon_dir, exist_ok=True)
                        ext = os.path.splitext(url)[1] or ".jpg"
                        icon_path = f"{icon_dir}/default{ext}"
                        if not os.path.exists(icon_path):
                            try:
                                r = requests.get(url, timeout=15)
                                r.raise_for_status()
                                with open(icon_path, "wb") as icf:
                                    icf.write(r.content)
                            except Exception:
                                pass
                        comment["icon_path"] = icon_path
                    else:
                        comment["icon_path"] = None
                else:
                    url = userpic_cache[posterid]
                    if url:
                        ext = os.path.splitext(url)[1] or ".jpg"
                        comment["icon_path"] = f"images/icons/{posterid}/default{ext}"
                    else:
                        comment["icon_path"] = None
        all_comments.extend(comments)

    with open('batch-downloads/comments-json/all.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(all_comments, ensure_ascii=False, indent=2))

    return all_comments


if __name__ == '__main__':
    download_comments()

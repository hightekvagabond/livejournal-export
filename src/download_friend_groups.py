#!/usr/bin/env python3
"""download_friend_groups.py

Utilities for fetching the authenticated user’s LiveJournal friend groups
(aka custom security filters).

Typical usage within the Docker container:

    from download_friend_groups import download_friend_groups
    groups = download_friend_groups(cookies, headers)

A small CLI wrapper is included, so you can also run the file directly once
cookies+headers are prepared by `export.py`.
"""

# NOTE: This script is now located in src/ and is intended to be run as a module or via Docker.
# All code is commented for clarity for junior developers.

from __future__ import annotations

import json
import sys
import os
from typing import Dict, List

import requests
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from download_posts import download_posts
from download_comments import download_comments
from download_friend_groups import download_friend_groups

# ---------------------------------------------------------------------------
# XML‑RPC helpers
# ---------------------------------------------------------------------------
RPC_URL = "https://www.livejournal.com/interface/xmlrpc"


def _rpc_call(method: str, params: Dict[str, str], cookies: Dict[str, str], headers: Dict[str, str]):
    """Low‑level XML‑RPC POST helper. Returns raw XML response text."""
    # Build a minimal XML‑RPC request
    xml_params = "".join(
        f"<param><value><string>{value}</string></value></param>" for value in params.values()
    )
    body = (
        f"<?xml version='1.0'?>"
        f"<methodCall><methodName>{method}</methodName><params>{xml_params}</params></methodCall>"
    )

    r = requests.post(RPC_URL, data=body, headers=headers, cookies=cookies, timeout=30)
    r.raise_for_status()
    return r.text


def _parse_friend_groups(xml_text: str) -> List[Dict]:
    """Parse <friendgroups> response into a list of dicts."""
    root = ET.fromstring(xml_text)
    members = root.findall(".//member[name='friendgroups']/value/array/data/value/struct")

    groups = []
    for struct in members:
        group_dict = {}
        for member in struct:
            name = member.findtext("name")
            value_elem = member.find("value/*[1]")  # first child of <value>
            group_dict[name] = value_elem.text or ""
        groups.append(group_dict)
    return groups


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_friend_groups(cookies: Dict[str, str], headers: Dict[str, str]) -> List[Dict]:
    """Return a list of friend‑group dicts using cookie authentication."""
    payload = {
        "auth_method": "cookie",
        "ver": "1",
    }
    xml_resp = _rpc_call("LJ.XMLRPC.getfriendgroups", payload, cookies, headers)
    return _parse_friend_groups(xml_resp)


# ---------------------------------------------------------------------------
# CLI helper for debugging
# ---------------------------------------------------------------------------

def _cli():
    import pathlib, json, os

    out_dir = pathlib.Path(os.environ.get("DEST", ".")) / "batch-downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "friend-groups.json"

    # Expect cookies + headers to be JSON on stdin (simple hack for debugging)
    blob = json.load(sys.stdin)
    groups = download_friend_groups(blob["cookies"], blob["headers"])
    out_file.write_text(json.dumps(groups, indent=2, ensure_ascii=False))
    print(f"Saved {len(groups)} groups → {out_file}")


if __name__ == "__main__":
    _cli()

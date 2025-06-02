#!/usr/bin/env python3
"""
LiveJournal exporter with optional CLI flags.

Required (for head-less mode)
  -u / --username
  -p / --password

Optional
  -s / --start   YYYY-MM  (default: 0000-01 = no lower bound)
  -e / --end     YYYY-MM  (default: 9999-12 = no upper bound)
  -f / --format  json|html|md  (default: json)
  -d / --dest    output folder (default: current dir)
"""
import argparse, getpass, json, os, re, sys
from datetime import datetime
from operator import itemgetter
from pathlib import Path

import html2text, requests
from bs4 import BeautifulSoup
from markdown import markdown
from download_posts import download_posts
from download_comments import download_comments

# ─── CLI / interactive ────────────────────────────────────────────────── #
def parse_cli():
    p = argparse.ArgumentParser()
    p.add_argument("-u", "--username")
    p.add_argument("-p", "--password")
    p.add_argument("-s", "--start", default="0000-01")
    p.add_argument("-e", "--end",   default="9999-12")
    p.add_argument("-f", "--format", default="json", choices=["json","html","md"])
    p.add_argument("-d", "--dest",   default=".")
    a = p.parse_args()

    if a.username and a.password:
        return a.username, a.password, a.start, a.end, a.format, a.dest
    return None  # triggers legacy prompt flow


def interactive():
    start = input("Enter start month YYYY-MM (empty = all): ").strip() or "0000-01"
    end   = input("Enter end month   YYYY-MM (empty = all): ").strip() or "9999-12"
    user  = input("Enter LiveJournal Username: ").strip()
    pw    = getpass.getpass("Enter LiveJournal Password: ")
    return user, pw, start, end, "json", os.getcwd()

# ─── Helpers ──────────────────────────────────────────────────────────── #
GENERIC_HEADERS = {
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": ("Mozilla/5.0 LiveJournalBackup"),
    "sec-ch-ua": '"Chromium";v="127"',
    "sec-ch-ua-platform": '"Linux"',
}
UA_API = "https://github.com/hightekvagabond/livejournal-export"


def get_ck(resp, name):
    hdr = resp.headers.get("Set-Cookie", "")
    if f"{name}=" not in hdr:
        raise RuntimeError(f"cookie {name} missing")
    return hdr.split(f"{name}=")[1].split(";")[0]


def month_ok(date_str: str | None, lo: str, hi: str) -> bool:
    """True if date_str (YYYY-MM-DD …) within range; if date_str missing return True."""
    if not date_str:
        return True
    m = date_str[:7]
    return lo <= m <= hi


# ─── Main ─────────────────────────────────────────────────────────────── #
def main():
    user, pw, start, end, out_fmt, dest = parse_cli() or interactive()
    Path(dest).mkdir(parents=True, exist_ok=True)
    os.chdir(dest)

    # pre-cookie + login
    pre = requests.get("https://www.livejournal.com/", headers=GENERIC_HEADERS)
    cookies = {"luid": get_ck(pre, "luid")}
    r = requests.post(
        "https://www.livejournal.com/login.bml",
        data={"user": user, "password": pw},
        cookies=cookies,
        headers=GENERIC_HEADERS,
    )
    if r.status_code != 200:
        sys.exit(f"login failed ({r.status_code})")

    cookies = {
        "ljloggedin":    get_ck(r, "ljloggedin"),
        "ljmastersession": get_ck(r, "ljmastersession"),
    }
    api_hdr = {"User-Agent": UA_API}

    print("Login OK – downloading …")
    posts    = [p for p in download_posts(cookies, api_hdr)     if month_ok(p["date"],                   start, end)]
    comments = [c for c in download_comments(cookies, api_hdr)  if month_ok(c.get("date", c.get("time")), start, end)]

    combine(posts, comments, out_fmt)
    print("Done →", Path(dest).resolve())

# ─── unchanged legacy render/combine code below … ─────────────────────── #
#   (identical to earlier version, omitted here for brevity)
# ------------------------------------------------------------------------
if __name__ == "__main__":
    main()


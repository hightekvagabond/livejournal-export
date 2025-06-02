#!/usr/bin/env python3
"""
Extended LiveJournal exporter with optional CLI flags.

Required for head-less mode:
  -u / --username
  -p / --password
  -s / --start   (YYYY-MM)
  -e / --end     (YYYY-MM)

Optional:
  -f / --format  json|html|md  (default: json)
  -d / --dest    output folder (default: .)
"""
import argparse
import getpass
import json
import os
import re
import sys
from datetime import datetime
from operator import itemgetter
from pathlib import Path

import html2text
import requests
from bs4 import BeautifulSoup
from markdown import markdown

from download_posts import download_posts
from download_comments import download_comments

# ─────────────────── CLI / interactive ──────────────────────────────────── #


def parse_cli():
    p = argparse.ArgumentParser()
    p.add_argument("-u", "--username")
    p.add_argument("-p", "--password")
    p.add_argument("-s", "--start", help="first month YYYY-MM")
    p.add_argument("-e", "--end", help="last month YYYY-MM")
    p.add_argument(
        "-f",
        "--format",
        default="json",
        choices=["json", "html", "md"],
        help="output format (default: json)",
    )
    p.add_argument(
        "-d",
        "--dest",
        default=".",
        help="destination folder (default: current dir)",
    )
    args = p.parse_args()
    if all([args.username, args.password, args.start, args.end]):
        return (
            args.username,
            args.password,
            args.start,
            args.end,
            args.format,
            args.dest,
        )
    return None


def interactive():
    start = input("Enter start month in YYYY-MM format: ").strip()
    end = input("Enter end month in YYYY-MM format: ").strip()
    username = input("Enter LiveJournal Username: ").strip()
    password = getpass.getpass("Enter LiveJournal Password: ")
    return username, password, start, end, "json", os.getcwd()


# ─────────────────── HTTP helpers ───────────────────────────────────────── #


def get_cookie_value(resp, cname):
    header = resp.headers.get("Set-Cookie")
    if not header or f"{cname}=" not in header:
        raise ValueError(f"Cookie {cname} not found")
    return header.split(f"{cname}=")[1].split(";")[0]


GENERIC_HEADERS = {
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Chromium";v="127"',
    "sec-ch-ua-platform": '"Windows"',
}

UA_API = "https://github.com/hightekvagabond/livejournal-export"


# ─────────────────── Main ───────────────────────────────────────────────── #


def month_ok(date_str: str, start: str, end: str) -> bool:
    """Return True if date is between start & end months inclusive."""
    m = date_str[:7]  # YYYY-MM
    return start <= m <= end


def main():
    cli = parse_cli() or interactive()
    user, pw, start, end, out_fmt, dest = cli

    dest_path = Path(dest).resolve()
    dest_path.mkdir(parents=True, exist_ok=True)
    os.chdir(dest_path)

    # Pre-login cookie
    pre = requests.get("https://www.livejournal.com/", headers=GENERIC_HEADERS)
    cookies = {"luid": get_cookie_value(pre, "luid")}

    # Login
    creds = {"user": user, "password": pw}
    r = requests.post(
        "https://www.livejournal.com/login.bml",
        data=creds,
        cookies=cookies,
        headers=GENERIC_HEADERS,
    )
    if r.status_code != 200:
        print("Login failed (HTTP", r.status_code, ")", file=sys.stderr)
        sys.exit(1)

    cookies = {
        "ljloggedin": get_cookie_value(r, "ljloggedin"),
        "ljmastersession": get_cookie_value(r, "ljmastersession"),
    }
    api_headers = {"User-Agent": UA_API}

    print("Login successful. Downloading posts and comments …")

    all_posts = download_posts(cookies, api_headers)
    all_comments = download_comments(cookies, api_headers)

    # Filter by month range
    posts_filtered = [
        p for p in all_posts if month_ok(p["date"], start, end)
    ]
    comments_filtered = [
        c for c in all_comments if month_ok(c["date"], start, end)
    ]

    combine(posts_filtered, comments_filtered, out_fmt)
    print("Done. Output saved to", dest_path)


# ─────────────────── Legacy render / combine code (unchanged) ───────────── #

COMMENTS_HEADER = "Комментарии"
TAG = re.compile(r"\[!\[(.*?)\]\(http:\/\/utx.ambience.ru\/img\/.*?\)\]\(.*?\)")
USER = re.compile(r'<lj user="?(.*?)"?>')
TAGLESS_NEWLINES = re.compile(r"(?<!>)\n")
NEWLINES = re.compile(r"(\s*\n){3,}")
SLUGS = {}


def fix_user_links(js):
    if "subject" in js:
        js["subject"] = USER.sub(r"\1", js["subject"])
    if "body" in js:
        js["body"] = USER.sub(r"\1", js["body"])


def json_to_html(js):
    return (
        "<!doctype html>\n<meta charset='utf-8'>\n"
        "<title>{subject}</title>\n<article>\n<h1>{subject}</h1>\n{body}\n</article>\n"
    ).format(
        subject=js["subject"] or js["date"],
        body=TAGLESS_NEWLINES.sub("<br>\n", js["body"]),
    )


def get_slug(js):
    slug = js["subject"] or js["id"]
    if "<" in slug or "&" in slug:
        slug = BeautifulSoup(f"<p>{slug}</p>", "lxml").text
    slug = re.compile(r"\W+").sub("-", slug)
    slug = re.compile(r"^-|-$").sub("", slug)
    if slug in SLUGS:
        slug += (slug and "-" or "") + js["id"]
    SLUGS[slug] = True
    return slug


def json_to_markdown(js):
    body = TAGLESS_NEWLINES.sub("<br>", js["body"])
    h = html2text.HTML2Text()
    h.body_width = 0
    h.unicode_snob = True
    body = h.handle(body)
    body = NEWLINES.sub("\n\n", body)
    tags = TAG.findall(body)
    js["tags"] = f"\ntags: {', '.join(tags)}" if tags else ""
    js["body"] = TAG.sub("", body).strip()
    js["slug"] = get_slug(js)
    js["subject"] = js["subject"] or js["date"]
    return (
        "id: {id}\n"
        "title: {subject}\n"
        "slug: {slug}\n"
        "date: {date}{tags}\n\n"
        "{body}\n"
    ).format(**js)


def group_comments_by_post(comments):
    posts = {}
    for c in comments:
        posts.setdefault(c["jitemid"], {})[c["id"]] = c
    return posts


def nest_comments(comments):
    root = []
    for c in comments.values():
        fix_user_links(c)
        if "parentid" not in c:
            root.append(c)
        else:
            comments[c["parentid"]].setdefault("children", []).append(c)
    return root


def comment_to_li(c):
    if c.get("state") == "D":
        return ""
    html = f"<h3>{c.get('author','anonym')}: {c.get('subject','')}</h3>"
    html += f"\n<a id='comment-{c['id']}'></a>"
    if "body" in c:
        html += "\n" + markdown(TAGLESS_NEWLINES.sub("<br>\n", c["body"]))
    if c.get("children"):
        html += "\n" + comments_to_html(c["children"])
    subj_cls = " class=subject" if "subject" in c else ""
    return f"<li{subj_cls}>{html}\n</li>"


def comments_to_html(comments):
    items = "\n".join(
        comment_to_li(c) for c in sorted(comments, key=itemgetter("id"))
    )
    return f"<ul>\n{items}\n</ul>"


def save_as_json(pid, post, comments, out_fmt):
    if out_fmt != "json":
        return
    Path("posts-json").mkdir(exist_ok=True)
    with open(f"posts-json/{pid}.json", "w", encoding="utf-8") as f:
        json.dump({"id": pid, "post": post, "comments": comments}, f, ensure_ascii=False, indent=2)


def save_as_markdown(pid, subfolder, post, comments_html, out_fmt):
    if out_fmt != "md":
        return
    Path(f"posts-markdown/{subfolder}").mkdir(parents=True, exist_ok=True)
    with open(f"posts-markdown/{subfolder}/{pid}.md", "w", encoding="utf-8") as f:
        f.write(json_to_markdown(post))
    if comments_html:
        with open(f"comments-markdown/{post['slug']}.md", "w", encoding="utf-8") as f:
            f.write(comments_html)


def save_as_html(pid, subfolder, post, comments_html, out_fmt):
    if out_fmt != "html":
        return
    Path(f"posts-html/{subfolder}").mkdir(parents=True, exist_ok=True)
    with open(f"posts-html/{subfolder}/{pid}.html", "w", encoding="utf-8") as f:
        f.write(json_to_html(post))
        if comments_html:
            f.write(f"\n<h2>{COMMENTS_HEADER}</h2>\n{comments_html}")


def combine(posts, comments, out_fmt):
    Path("comments-markdown").mkdir(exist_ok=True)
    posts_comments = group_comments_by_post(comments)

    for post in posts:
        pid = post["id"]
        jitemid = int(pid) >> 8
        date = datetime.strptime(post["date"], "%Y-%m-%d %H:%M:%S")
        subfolder = f"{date.year}-{date.month:02d}"

        post_comments = (
            nest_comments(posts_comments[jitemid])
            if jitemid in posts_comments
            else None
        )
        comments_html = comments_to_html(post_comments) if post_comments else ""
        fix_user_links(post)

        save_as_json(pid, post, post_comments, out_fmt)
        save_as_html(pid, subfolder, post, comments_html, out_fmt)
        save_as_markdown(pid, subfolder, post, comments_html, out_fmt)


if __name__ == "__main__":
    main()


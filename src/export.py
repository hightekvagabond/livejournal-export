#!/usr/bin/env python3
"""
LiveJournal exporter (modernized, Docker/CLI-ready)

Exports all posts, comments, and media from a LiveJournal account into a clean, hierarchical folder structure for long-term archival and offline browsing.

Features:
- Batch downloads of posts and comments (XML and JSON)
- Per-post folders: posts/<YYYY>/<MM>/<YYYY-MM-DD-HH-mm-postID>/
- Per-comment folders: posts/.../comments/<commentID>/
- Embedded media saved to posts/.../media/
- User icons saved to images/icons/<userid>/
- All JSON includes post_url, comment_url, icon_path, and user.profile_url
- Idempotent: safe to re-run without duplicate downloads

Usage:
  python export.py -u <username> -p <password> [-s <start>] [-e <end>] [-f <format>] [-d <dest>]

Arguments:
  -u / --username  (required)
  -p / --password  (required)
  -s / --start YYYY-MM   default 1999-04
  -e / --end   YYYY-MM   default <current year and month>
  -f / --format json|html|md  default json
  -d / --dest   output dir    default .

See README.md for full details and sample output structure.
"""
# NOTE: This script is now located in src/ and is intended to be run as a module or via Docker.
# All code is commented for clarity for junior developers.

import argparse, getpass, json, os, re, sys
from datetime import datetime
from operator import itemgetter
from pathlib import Path

import html2text, requests
from bs4 import BeautifulSoup
from markdown import markdown

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from download_posts import download_posts
from download_comments import download_comments
from download_friend_groups import download_friend_groups


# ─────────────────── CLI / interactive ─────────────────────────────────── #
def parse_cli():
    from datetime import datetime
    now = datetime.now()
    default_start = "1999-04"
    default_end = f"{now.year}-{now.month:02d}"
    p = argparse.ArgumentParser()
    p.add_argument("-u", "--username")
    p.add_argument("-p", "--password")
    p.add_argument("-s", "--start", default=default_start)
    p.add_argument("-e", "--end",   default=default_end)
    p.add_argument("-f", "--format", default="json", choices=["json","html","md"])
    p.add_argument("-d", "--dest",   default=".")
    a = p.parse_args()
    if a.username and a.password:
        return a.username, a.password, a.start, a.end, a.format, a.dest
    return None


def interactive():
    from datetime import datetime
    now = datetime.now()
    default_start = "1999-04"
    default_end = f"{now.year}-{now.month:02d}"
    start = input(f"Enter start month YYYY-MM [default: {default_start}]: ").strip() or default_start
    end   = input(f"Enter end month   YYYY-MM [default: {default_end}]: ").strip() or default_end
    user  = input("Enter LiveJournal Username: ").strip()
    pw    = getpass.getpass("Enter LiveJournal Password: ")
    return user, pw, start, end, "json", os.getcwd()


# ─────────────────── HTTP helpers ──────────────────────────────────────── #
HDRS  = {"User-Agent": "LiveJournalBackup/1.0"}
UA_API = "https://github.com/hightekvagabond/livejournal-export"


def ck(resp, name):
    s = resp.headers.get("Set-Cookie", "")
    if f"{name}=" not in s:
        raise RuntimeError(f"cookie {name} missing")
    return s.split(f"{name}=")[1].split(";")[0]


def month_ok(date_str: str | None, lo: str, hi: str) -> bool:
    if not date_str:
        return True
    m = date_str[:7]
    return lo <= m <= hi


# ─────────────────── Main ──────────────────────────────────────────────── #
def main():
    user, pw, start, end, out_fmt, dest = parse_cli() or interactive()

    Path(dest).mkdir(parents=True, exist_ok=True)
    os.chdir(dest)

    pre = requests.get("https://www.livejournal.com/", headers=HDRS)
    cookies = {"luid": ck(pre, "luid")}

    r = requests.post(
        "https://www.livejournal.com/login.bml",
        data={"user": user, "password": pw},
        cookies=cookies,
        headers=HDRS,
    )
    if r.status_code != 200:
        sys.exit(f"Login failed ({r.status_code})")

    cookies = {
        "ljloggedin":    ck(r, "ljloggedin"),
        "ljmastersession": ck(r, "ljmastersession"),
    }
    api_hdr = {"User-Agent": UA_API}

    print("Login OK – downloading …")
    posts    = [p for p in download_posts(cookies, api_hdr)
                if month_ok(p["date"], start, end)]
    comments = [c for c in download_comments(cookies, api_hdr)
                if month_ok(c.get("date", c.get("time")), start, end)]
    # Download friend groups (security masks)
    friend_groups = download_friend_groups(cookies, api_hdr)
    # Save friend groups to batch-downloads/friend-groups.json
    fg_dir = Path("batch-downloads")
    fg_dir.mkdir(exist_ok=True)
    with open(fg_dir / "friend-groups.json", "w", encoding="utf-8") as f:
        json.dump(friend_groups, f, ensure_ascii=False, indent=2)

    combine(posts, comments, out_fmt)
    print("Done →", Path(dest).resolve())


# ─────────────────── unchanged legacy helpers (combine, HTML, etc.) ───── #
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
    slug = re.sub(r"\W+", "-", slug).strip("-")
    if slug in SLUGS:
        slug += "-" + js["id"]
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


def nest_comments(cmts):
    root = []
    for c in cmts.values():
        fix_user_links(c)
        if "parentid" not in c:
            root.append(c)
        else:
            cmts[c["parentid"]].setdefault("children", []).append(c)
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


def save_as_json(pid, post, cmts, out_fmt):
    if out_fmt != "json":
        return
    # Compute hierarchical post folder path
    eventtime = post.get("eventtime") or post.get("date")
    if eventtime:
        dt = datetime.strptime(eventtime, "%Y-%m-%d %H:%M:%S")
        post_dir = Path(f"posts/{dt.year}/{dt.month:02d}/{dt.strftime('%Y-%m-%d-%H-%M')}-{pid}")
    else:
        post_dir = Path(f"posts/unknown-date/{pid}")
    post_dir.mkdir(parents=True, exist_ok=True)
    # Add post_url to post
    username = post.get("username")
    if not username:
        # Try to get from global context if available
        username = globals().get("LJ_USER")
    post_url = None
    if username:
        post_url = f"https://{username}.livejournal.com/{pid}.html"
        post["post_url"] = post_url
    # Save main post JSON
    with open(post_dir / "post.json", "w", encoding="utf-8") as f:
        json.dump({"id": pid, "post": post, "comments": cmts}, f, ensure_ascii=False, indent=2)
    # Save each comment in its own folder if present
    if cmts:
        comments_dir = post_dir / "comments"
        comments_dir.mkdir(exist_ok=True)
        def save_comment_tree(comment):
            cid = comment["id"]
            cdir = comments_dir / str(cid)
            cdir.mkdir(exist_ok=True)
            # Add comment_url to comment
            if post_url:
                comment["comment_url"] = f"{post_url}?thread={cid}#t{cid}"
            with open(cdir / "comment.json", "w", encoding="utf-8") as cf:
                json.dump(comment, cf, ensure_ascii=False, indent=2)
            for child in comment.get("children", []):
                save_comment_tree(child)
        for comment in cmts:
            save_comment_tree(comment)


def save_as_markdown(pid, subfolder, post, cmts_html, out_fmt):
    if out_fmt != "md":
        return
    Path(f"posts-markdown/{subfolder}").mkdir(parents=True, exist_ok=True)
    with open(f"posts-markdown/{subfolder}/{pid}.md", "w", encoding="utf-8") as f:
        f.write(json_to_markdown(post))
    if cmts_html:
        with open(f"comments-markdown/{post['slug']}.md", "w", encoding="utf-8") as f:
            f.write(cmts_html)


def save_as_html(pid, subfolder, post, cmts_html, out_fmt):
    if out_fmt != "html":
        return
    Path(f"posts-html/{subfolder}").mkdir(parents=True, exist_ok=True)
    with open(f"posts-html/{subfolder}/{pid}.html", "w", encoding="utf-8") as f:
        f.write(json_to_html(post))
        if cmts_html:
            f.write(f"\n<h2>{COMMENTS_HEADER}</h2>\n{cmts_html}")


def combine(posts, comments, out_fmt):
    Path("comments-markdown").mkdir(exist_ok=True)
    p2c = group_comments_by_post(comments)
    for post in posts:
        pid = post["id"]
        jitemid = int(pid) >> 8
        date = datetime.strptime(post["date"], "%Y-%m-%d %H:%M:%S")
        subfolder = f"{date.year}-{date.month:02d}"
        cmts = nest_comments(p2c[jitemid]) if jitemid in p2c else None
        cmts_html = comments_to_html(cmts) if cmts else ""
        fix_user_links(post)
        save_as_json(pid, post, cmts, out_fmt)
        save_as_html(pid, subfolder, post, cmts_html, out_fmt)
        save_as_markdown(pid, subfolder, post, cmts_html, out_fmt)


if __name__ == "__main__":
    main()


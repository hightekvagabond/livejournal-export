#!/usr/bin/env python3
"""
LiveJournal exporter (fork, CLI-enhanced).

Head-less flags
---------------

  -u / --username  (required)
  -p / --password  (required)
  -s / --start YYYY-MM   default 0000-01
  -e / --end   YYYY-MM   default 9999-12
  -f / --format json|html|md  default json
  -d / --dest   output dir    default .

If -u/-p are missing, falls back to the original interactive prompts.
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


# ─────────────────── CLI / interactive ─────────────────────────────────── #
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
    return None


def interactive():
    start = input("Enter start month YYYY-MM (empty = all): ").strip() or "0000-01"
    end   = input("Enter end month   YYYY-MM (empty = all): ").strip() or "9999-12"
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


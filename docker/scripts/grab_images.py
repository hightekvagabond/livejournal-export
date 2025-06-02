#!/usr/bin/env python3
import sys, os, json, pathlib, requests, tqdm
from bs4 import BeautifulSoup

ROOT = pathlib.Path(sys.argv[1]).expanduser()
POSTS = ROOT / "posts-json"
IMG_DIR = ROOT / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

for jf in tqdm.tqdm(list(POSTS.glob("*.json")), desc="scanning posts"):
    data = json.loads(jf.read_text())
    # Use post.body if body_html is not present
    body_html = data.get("body_html")
    if not body_html and "post" in data and "body" in data["post"]:
        body_html = data["post"]["body"]
    if not body_html:
        continue
    soup = BeautifulSoup(body_html, "lxml")
    comments = data.get("comments") or []
    for c in comments:
        soup.append(BeautifulSoup(c.get("body_html", c.get("body", "")), "lxml"))

    # Determine post date for folder structure
    post_date = None
    if "post" in data:
        post_date = data["post"].get("eventtime") or data["post"].get("date")
    if post_date:
        from datetime import datetime
        dt = datetime.strptime(post_date, "%Y-%m-%d %H:%M:%S")
        media_dir = ROOT / f"posts/{dt.year}/{dt.month:02d}/{dt.strftime('%Y-%m-%d-%H-%M')}-{data['id']}/media"
    else:
        media_dir = ROOT / f"posts/unknown-date/{data['id']}/media"
    media_dir.mkdir(parents=True, exist_ok=True)

    for img in soup.find_all("img", src=True):
        url = img["src"].split("?")[0]
        fname = media_dir / os.path.basename(url)
        print(f"Found image: {url} -> {fname}")
        if not fname.exists():
            try:
                r = requests.get(url, timeout=15)
                r.raise_for_status()
                fname.write_bytes(r.content)
                print(f"Downloaded: {fname}")
            except Exception as e:
                print(f"Failed to download {url}: {e}")
                continue
        img["src"] = f"media/{fname.name}"

    # Save back to the correct field
    if "body_html" in data:
        data["body_html"] = str(soup)
    elif "post" in data and "body" in data["post"]:
        data["post"]["body"] = str(soup)
    jf.write_text(json.dumps(data, ensure_ascii=False, indent=2))


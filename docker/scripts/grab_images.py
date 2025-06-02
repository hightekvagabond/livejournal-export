#!/usr/bin/env python3
import sys, os, json, pathlib, requests, tqdm
from bs4 import BeautifulSoup

ROOT = pathlib.Path(sys.argv[1]).expanduser()
POSTS = ROOT / "posts-json"
IMG_DIR = ROOT / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

for jf in tqdm.tqdm(list(POSTS.glob("*.json")), desc="scanning posts"):
    data = json.loads(jf.read_text())
    soup = BeautifulSoup(data["body_html"], "lxml")
    for c in data.get("comments", []):
        soup.append(BeautifulSoup(c["body_html"], "lxml"))

    for img in soup.find_all("img", src=True):
        url = img["src"].split("?")[0]
        fname = IMG_DIR / os.path.basename(url)
        if not fname.exists():
            try:
                r = requests.get(url, timeout=15)
                r.raise_for_status()
                fname.write_bytes(r.content)
            except Exception:
                continue
        img["src"] = f"images/{fname.name}"

    data["body_html"] = str(soup)
    jf.write_text(json.dumps(data, ensure_ascii=False, indent=2))


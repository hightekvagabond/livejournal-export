# LiveJournal-Export

A command-line tool to download **every** post, comment, and embedded image
from a LiveJournal account.  
Originally by [arty-name](https://github.com/arty-name/livejournal-export),
now enhanced with modern CLI flags and an optional Docker wrapper for fully
isolated runs.

---

## ✨ New in this fork

* **Non-interactive flags** – run head-less in scripts or cron:
  ```bash
  python export.py -u USER -p APPPASS \
                   -s 1999-01 -e 2025-06 \
                   -f json     -d /path/out

* `--start/--end` default to the entire history (0000-01 → 9999-12),
  so only `-u/-p` are strictly required.
* Works even when comment objects lack a `date` field.
* One-shot Docker build + `run_backup.sh` helper:

  ```bash
  ./run_backup.sh -d ~/backups/lj
  ```

---

## 1  Stand-alone Python usage

```bash
git clone https://github.com/hightekvagabond/livejournal-export.git
cd livejournal-export
python3 -m venv .venv && source .venv/bin/activate
pip install -r docker/requirements.txt      # reuse the same list

python export.py \
  -u myusername \
  -p my_app_password \
  -s 2000-01 \
  -e 2025-06 \
  -f json \
  -d ~/lj_archive
```

Output layout:

```
lj_archive/
├─ posts-json/        # one JSON per entry (nested comments, local image paths)
├─ posts-html/        # if -f html
├─ posts-markdown/    # if -f md
└─ images/            # downloaded pictures
```

---

## 2  Docker quick-start (recommended)

> Perfect when you don’t want Python deps on your host.

```bash
# 1. build (tagged with current commit hash)
docker build -f docker/Dockerfile -t ljexport:$(git rev-parse --short=12 HEAD) .

# 2. run once, interactively
bash run_backup.sh -d /absolute/path/for/archive
```

You can now use additional flags for testing and development:

- `--start YYYY-MM` and `--end YYYY-MM` to limit the date range (e.g. only download a few months)
- `--clear` to delete all contents of the destination folder before backup **and** remove all Docker images/containers with `ljexport:*` (useful for clean test runs and avoiding Docker cache issues)

Example:

```bash
./run_backup.sh --dest /tmp/ljtest --start 2010-01 --end 2010-03 --clear
```

This will only download posts/comments from Jan–Mar 2010, clear the output folder, and remove all ljexport Docker images/containers before starting.

`run_backup.sh` will:

1. read `LJ_USER` / `LJ_PASS` from `.env`, or fetch them from Bitwarden CLI,
   or prompt you;
2. auto-build the image for the current commit if it doesn’t exist;
3. bind-mount your chosen archive folder;
4. execute `src/lj_full_backup.sh` inside the container, which in
   turn runs `export.py` and `grab_images.py`.

Subsequent runs build a **new** image only when the commit hash changes.

---

## 3  CLI flag reference

| Flag               | Required | Default   | Meaning                           |
| ------------------ | -------- | --------- | --------------------------------- |
| `-u`, `--username` | ✅        | –         | LiveJournal login name            |
| `-p`, `--password` | ✅        | –         | Plain or app-password             |
| `-s`, `--start`    | ▫️       | `0000-01` | First month to export (`YYYY-MM`) |
| `-e`, `--end`      | ▫️       | `9999-12` | Last month to export (`YYYY-MM`)  |
| `-f`, `--format`   | ▫️       | `json`    | `json`, `html`, or `md`           |
| `-d`, `--dest`     | ▫️       | `.`       | Destination directory             |

If either `-u` or `-p` is omitted, the script falls back to the legacy prompts
(start month, end month, user, pass).

---

## 4  Incremental backups

`export.py` re-downloads everything each run (cheap, thanks to LJ limits), but
`grab_images.py` skips files that already exist, so it’s safe to cron weekly:

```bash
0 4 * * 0 cd /path/to/livejournal-export && \
          ./run_backup.sh -d /mnt/archive/lj >> /var/log/ljbackup.log 2>&1
```

---

## 5  Prerequisites

| Need                         | Why                         | Install                                                                    |
| ---------------------------- | --------------------------- | -------------------------------------------------------------------------- |
| **Python 3.9+** (non-Docker) | run `export.py` directly    | system pkg / `pyenv`                                                       |
| **Docker** (optional)        | container workflow          | [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/) |
| **jq** + **Bitwarden CLI**   | auto-fetch creds (optional) | `apt install jq bw` / `brew install jq bw`                                 |

For 2-factor LJ accounts create an “app-password” under **Account → Passwords → App Passwords**.

---

## 6  Project layout (v0.2.0+)

```
.
├─ src/
│   ├─ export.py                  # main script (with argparse)
│   ├─ download_posts.py
│   ├─ download_comments.py
│   ├─ download_friend_groups.py
│   ├─ grab_images.py
│   └─ lj_full_backup.sh
├─ Refactoring.md
├─ README.md
├─ run_backup.sh                  # root-level Docker entry point
├─ posts/                         # per-post folders (YYYY/MM/...) with post.json, media/, comments/
├─ images/
│   └─ icons/<userid>/            # user icons
├─ batch-downloads/
│   ├─ posts-xml/                 # monthly post XMLs
│   ├─ comments-xml/              # comment XMLs
│   ├─ posts-json/                # all.json, per-post JSONs
│   └─ comments-json/             # all.json, per-comment JSONs
└─ docker/
    ├─ Dockerfile
    ├─ requirements.txt
    └─ scripts/
        └─ grab_images.py         # legacy location, not used in Docker anymore
```

- All Python scripts are now in `src/`.
- `run_backup.sh` is the main entry point for Docker-based workflows.
- `src/lj_full_backup.sh` is called inside the container (not directly by users).
- The legacy `README_orig.md` has been removed; all up-to-date usage is in this README.
- See `Refactoring.md` for migration details and workflow.

---

## 7  Troubleshooting

| Symptom                        | Fix                                                                      |
| ------------------------------ | ------------------------------------------------------------------------ |
| Prompts still appear           | Make sure you provided `-u/-p` *or* set them in `.env`.                  |
| `KeyError: 'date'` on comments | You’re on an old commit; pull latest (the patch handles missing `date`). |
| Docker image never rebuilds    | You forgot to commit; the hash didn’t change.                            |
| LiveJournal returns 403        | Use an **app-password** instead of your normal one.                      |

---

## 8  License & credits

*Code*: MIT.
*Upstream inspiration*: original exporter by **arty-name** (Apache 2.0).
Fork updates & Docker wrapper by **hightekvagabond**.

PRs welcome—happy archiving!



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

* `--start/--end` default to the entire history (**1999-04** → now), so only `-u/-p` are strictly required.
  - **Note:** The default start date is April 1999 (`1999-04`), which is when LiveJournal first opened to the public. This ensures you capture all possible posts for any account.
* Works even when comment objects lack a `date` field.
* One-shot Docker build + `run_backup.sh` helper:

  ```bash
  ./run_backup.sh -d ~/backups/lj
  ```

---

## 0  Environment file (.env) workflow

This project supports a `.env` file for all configuration. Copy `env.example` to `.env` and fill in your values:

```bash
cp env.example .env
# Edit .env with your credentials and options
```

Supported variables in `.env`:

- `LJ_USER`   – LiveJournal username (required)
- `LJ_PASS`   – LiveJournal password or app-password (required)
- `DEST`      – Output directory (required)
- `START`     – Start month (YYYY-MM, optional, default: 1999-04)
- `END`       – End month (YYYY-MM, optional, default: now)
- `FORMAT`    – Output format: json, html, or md (optional, default: json)
- `CLEAR`     – Set to true to clear destination and Docker images before backup (optional)

**Precedence:** CLI flags > `.env` > interactive prompt. Any variable not set in `.env` can be provided as a CLI flag to `run_backup.sh`. If both are set, the CLI flag takes precedence.

See `env.example` for full documentation and best practices.

---

## 1  Recommended: Run with `run_backup.sh` (Docker + Bash)

This is the easiest and most robust way to run the exporter. It requires Docker and Bash (Linux/macOS/WSL).

### 🔐 Secure credentials: Bitwarden CLI support

For maximum security, you can use the [Bitwarden CLI](https://bitwarden.com/help/cli/) to provide your LiveJournal credentials at runtime. If Bitwarden CLI (`bw`) and `jq` are installed and unlocked, `run_backup.sh` will prompt you to select a credential containing "livejournal" from your Bitwarden vault. This avoids storing your password in plaintext on disk.

- If Bitwarden CLI is available, leave `LJ_USER` and `LJ_PASS` blank in your `.env` file (or unset them in your shell).
- The script will search for items with "livejournal" in the name and let you pick the correct one.
- If Bitwarden is not available, it will fall back to `.env`, CLI flags, or prompt you interactively.

---

You can also use CLI flags or a `.env` file for configuration:

```bash
./run_backup.sh --dest /absolute/path/for/archive \
                --start 2010-01 --end 2010-03
```

Or, with a `.env` file:

```bash
cp env.example .env
# Edit .env with your credentials and options
./run_backup.sh
```

### Supported flags for `run_backup.sh`

| Flag               | Required | Default   | Meaning                           |
| ------------------ | -------- | --------- | --------------------------------- |
| `-d`, `--dest`     | ✅        | –         | Host directory for archive        |
| `-s`, `--start`    | ▫️       | `1999-04` | First month to export (`YYYY-MM`) |
| `-e`, `--end`      | ▫️       | `now`     | Last month to export (`YYYY-MM`)  |
| `--clear`          | ▫️       | `false`   | Clear dest & Docker images first  |
| `-h`, `--help`     | ▫️       |           | Show help and exit                |

- All variables can also be set in `.env` (see `env.example`).
- CLI flags take precedence over `.env`.
- Credentials can be provided via `.env`, CLI, or Bitwarden CLI integration.

### Output layout

```
archive/
├─ posts/                # per-post folders (YYYY/MM/...) with post.json, media/, comments/
├─ images/               # downloaded user icons
├─ batch-downloads/
│   ├─ posts-xml/        # monthly post XMLs
│   ├─ comments-xml/     # comment XMLs
│   ├─ posts-json/       # all.json, per-post JSONs
│   └─ comments-json/    # all.json, per-comment JSONs
```

---

## 2  Run in Docker manually

If you want to run the exporter in Docker without the helper script:

```bash
# 1. build (tagged with current commit hash)
docker build -f docker/Dockerfile -t ljexport:$(git rev-parse --short=12 HEAD) .

# 2. run interactively
export LJ_USER=youruser
export LJ_PASS=yourpass
export START_MONTH=2010-01
export END_MONTH=2010-03
export DEST=/absolute/path/for/archive

docker run --rm -it \
  -e LJ_USER -e LJ_PASS -e START_MONTH -e END_MONTH -e DEST \
  -v "$DEST":/backup \
  ljexport:$(git rev-parse --short=12 HEAD) \
  /opt/livejournal-export/src/lj_full_backup.sh
```

---

## 3  Stand-alone Python usage

If you want to run the exporter directly in Python (no Docker):

```bash
git clone https://github.com/hightekvagabond/livejournal-export.git
cd livejournal-export
python3 -m venv .venv && source .venv/bin/activate
pip install -r docker/requirements.txt

python src/export.py \
  -u myusername \
  -p my_app_password \
  -s 2000-01 \
  -e 2025-06 \
  -f json \
  -d ~/lj_archive
```

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



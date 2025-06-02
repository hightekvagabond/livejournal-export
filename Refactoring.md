ok, I've created a refactoring list in this file, I want you to create a new feature branch for this set of refactors, do them one at a time, then test them, after wards let push the feature branch in the current version and let me test it manually before you move to the next one. Once it is complete you can mark it in the refactor list as done, but do not delete the refactor list or anything from it until the whole thing is approved by me.

---

### 1 — Create the new top-level folder layout

**Why:** We need a clean, predictable structure that separates raw batch dumps, images, and per-post data.

* **Folders to create at runtime**

  ```
  batch-downloads/
  images/
  posts/
  ```
* **Files to edit**

  * `docker/scripts/lj_full_backup.sh` – `mkdir` these three paths before export starts.
  * `export.py` – change any hard-coded default output paths to the new root directories.

---

### 2 — Move monthly post XML files into `batch-downloads/posts-xml/`

**Why:** Those XMLs are rarely used except for disaster recovery; they shouldn’t clutter the main data tree.

* **Files to edit**

  * `export.py` (or whichever helper currently writes the XML files).
  * `download_posts.py` if it saves XML directly.
* **Work:** Save each month’s XML as
  `batch-downloads/posts-xml/<YYYY-MM>.xml`.

---

### 3 — Move comment XML dumps into `batch-downloads/comments-xml/`

**Why:** Same reasoning as above for comments.

* **Files to edit**

  * `download_comments.py`.
* **Work:**

  * Metadata file → `comment_meta.xml`
  * Body chunks → `comment_body-XXX.xml`
    under `batch-downloads/comments-xml/`.

---

### 4 — Move the giant “all.json” summary files into `batch-downloads/posts-json/` and `batch-downloads/comments-json/`

**Why:** They are useful for quick greps but not part of the per-post archive.

* **Files to edit**

  * `export.py` JSON-save logic.

---

### 5 — Introduce hierarchical post folders under `posts/`

`posts/<YYYY>/<MM>/<YYYY-MM-DD-HH-mm-postID>/`

**Why:** Makes it trivial to browse posts chronologically and avoids 1-directory-with-thousands-of-files.

* **Files to edit**

  * `export.py` – in each `save_as_*` helper, compute the folder path from the post’s timestamp.
  * Remove logic that pre-creates empty month folders; only create them when needed.
* **API to consult**
  `LJ.XMLRPC.getevents` – used already; just extract `eventtime`.

---

### 6 — Add a `media/` subfolder inside every post directory

**Why:** Keep embedded pictures/videos local to the post.

* **Files to edit**

  * `docker/scripts/grab_images.py`.
* **Work:**

  * Scan post HTML for `<img>` / `<video>` etc.
  * Download each asset into `posts/.../media/`.
  * Rewrite the HTML in the post JSON to refer to the local relative path.

---

### 7 — Create per-comment folders under each post

`posts/.../comments/<commentID>/`

**Why:** Allows random access to individual comments and their media.

* **Files to edit**

  * `export.py` – when iterating comments, save each into its own directory.
  * `grab_images.py` – download any media in the comment body into `comments/<id>/media/`.
* **LiveJournal API reference**
  `comments.get` (XML-RPC) returns `commentid`, `posterid`, `postername`, `body`, `userpicid`, `time`, etc.

---

### 8 — Download user icons once, store in `images/icons/<userid>/`

**Why:** Re-use icons and avoid redownloading.

* **Files to edit**

  * `download_comments.py` (or new helper) – call `userpics.get` once per unique `posterid`.
  * `grab_images.py` – if icon not present, download it.
* **JSON update:** Add to each comment:

  ```json
  "icon_path": "images/icons/12345/default.jpg"
  ```

---

### 9 — Add URL metadata to each post and comment JSON

**Why:** Makes it easy to open the original discussion from the archive.

* **Files to edit**

  * `export.py` when building JSON blobs.
* **How to build URLs**

  * Post: `https://<username>.livejournal.com/<itemid>.html`
  * Comment: same URL + `?thread=<commentID>#t<commentID>`.
    (Username comes from login; no hard-coding.)

---

### 10 — Update `export.py` docstring and root `README.md`

**Why:** Docs must match code; new users need correct paths & flags.

* **Files to edit**

  * `export.py` – top-of-file description block.
  * `README.md` (root) – replace old layout, show new sample structure, docker usage.

---

### 11 — Add clean-up of legacy paths after a successful run

**Why:** Avoid confusion when old folders remain from earlier versions.

* **Files to edit**

  * `docker/scripts/lj_full_backup.sh` – after export + image grab, `rmdir` any now-empty `posts-json/*`, `comments-json/*`, etc. Be sure to check they’re empty before deleting.

---

### 12 — Manual QA + tag a release

**Why:** Ensure each refactor step is stable before public release.

* **Tasks**

  1. Run `./run_backup.sh` against a small date range (e.g., one month) and verify:

     * post folders created correctly
     * comment subfolders present
     * icon files saved under `images/icons/`
     * JSON includes new fields (`post_url`, `comment_url`, `icon_path`, `user.profile_url`)
  2. Run a second time to confirm idempotency (no duplicate downloads).
  3. Bump version in README and tag `v0.2.0`.

---

## Refactor Checklist (v0.2.0)

- [x] 1 — Create the new top-level folder layout
- [x] 2 — Move monthly post XML files into `batch-downloads/posts-xml/`
- [x] 3 — Move comment XML dumps into `batch-downloads/comments-xml/`
- [x] 4 — Move the giant “all.json” summary files into `batch-downloads/posts-json/` and `batch-downloads/comments-json/`
- [x] 5 — Introduce hierarchical post folders under `posts/`
- [x] 6 — Add a `media/` subfolder inside every post directory
- [x] 7 — Create per-comment folders under each post
- [x] 8 — Download user icons once, store in `images/icons/<userid>/`
- [x] 9 — Add URL metadata to each post and comment JSON
- [x] 10 — Update `export.py` docstring and root `README.md`
- [x] 11 — Add clean-up of legacy paths after a successful run (clarified: not needed)
- [ ] 12 — Manual QA + tag a release

---

**Do not delete this file or checklist until the entire refactor is approved and released.**

### References & docs

* LiveJournal XML-RPC spec: [https://stat.livejournal.com/doc/server/ljp.api.ref.html](https://stat.livejournal.com/doc/server/ljp.api.ref.html)

  * `getevents` – post content and metadata
  * `getcomments` – threaded comments
  * `userpics.get` – user icons
* Existing helper scripts: `download_posts.py`, `download_comments.py`.

---

### Workflow reminder

1. **Implement one checklist item.**
2. **Run `./run_backup.sh` on a test LJ account.**
3. **Commit, push, run unit tests if any.**
4. Move to the next item.


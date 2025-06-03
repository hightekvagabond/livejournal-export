# LiveJournal API Quick Reference: Userpics, Usernames, and Profile Links

**Date created:** 2025-06-03

## Purpose
This file summarizes the relevant LiveJournal API endpoints and methods for retrieving userpic, username, and profile information for posts and comments. If this file is more than one month old, refresh it from the official docs: https://stat.livejournal.com/doc/server/ljp.index.html

---

## Key API Methods

### 1. getevents (XML-RPC/Flat)
- Used to fetch journal entries (posts).
- Returns basic post data, but does **not** include userpic or username for each post/comment by default.
- See: https://stat.livejournal.com/doc/server/ljp.csp.xml-rpc.getevents.html

### 2. Export Comments (export_comments.bml)
- Used to fetch comments for a post.
- Returns comment data, including user IDs, but **not** userpic or username directly.
- See: https://stat.livejournal.com/doc/server/ljp.csp.export_comments.html

### 3. User Info (userinfo)
- To get userpic, username, and profile URL for a user ID, use the `LJ.XMLRPC.getuserinfo` method.
- See: https://stat.livejournal.com/doc/server/ljp.csp.xml-rpc.getuserinfo.html
- Input: list of usernames or userids
- Output: For each user, returns:
  - `userid`, `user`, `name`, `defaultpicurl`, `userpicurl`, `profile_url`, etc.

### 4. Userpic selection per post/comment
- The userpic used for a post is stored as a property (`prop_current_userpic` or similar) on the post.
- For comments, the userpic is referenced by a `userpicid` or similar field in the comment data.
- To resolve the actual image URL, use `getuserinfo` with the `userpicid` or fetch all userpics for a user and match by ID.

---

## Exporter Enhancement Plan
- When exporting posts/comments, collect the user ID, then call `getuserinfo` to get username, userpic, and profile URL.
- For each post/comment, if a userpic ID is present, resolve it to a URL using the user's userpics.
- Store these fields in the exported JSON:
  - `username`, `profile_url`, `userpic_url` (for both post author and each commenter)

---

## Refresh Rule
- If this file is more than 1 month old, re-check the official API docs for changes.

---

## References
- [LiveJournal API Index](https://stat.livejournal.com/doc/server/ljp.index.html)
- [getevents](https://stat.livejournal.com/doc/server/ljp.csp.xml-rpc.getevents.html)
- [export_comments](https://stat.livejournal.com/doc/server/ljp.csp.export_comments.html)
- [getuserinfo](https://stat.livejournal.com/doc/server/ljp.csp.xml-rpc.getuserinfo.html)

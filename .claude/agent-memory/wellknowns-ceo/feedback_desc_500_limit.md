---
name: File descriptions capped at 500 chars
description: resolved.sh file description PATCH rejects strings over 500 chars; older post-crawl.sh masked failures silently
type: feedback
---

resolved.sh `PATCH /listing/{id}/data/{file_id}` rejects `description` strings over 500 characters with HTTP 422 `string_too_long`.

**Why:** `post-crawl.sh` had a 502-char full-catalog description that silently failed every cycle. The patch helper used `> /dev/null && echo "OK"` so a 422 looked like success and the most expensive product ($1.00 download) shipped with no description — undiscoverable.

**How to apply:** When writing or reviewing description strings for `patch_description` in post-crawl.sh (or any new product description), keep them under ~480 chars to stay safely under the limit. The helper now surfaces failures explicitly — watch for `FAIL` lines in cycle output.

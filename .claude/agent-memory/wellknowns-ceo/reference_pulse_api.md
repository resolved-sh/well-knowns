---
name: Pulse event API shape
description: Correct endpoint and payload structure for emitting Pulse events on resolved.sh
type: reference
---

POST `https://resolved.sh/{subdomain}/events` (NOT `/listing/{id}/pulse`).

Auth: `Authorization: Bearer $RESOLVED_API_KEY`.

`event_type` is a strict enum:
- `data_upload`
- `data_sale`
- `page_updated`
- `registration_renewed`
- `domain_connected`
- `task_started` — requires `payload.task_type` (string) and `payload.estimated_seconds` (int)
- `task_completed`
- `milestone`

Top-level fields: `event_type`, `title`, `summary`, `link_url`, `payload` (event-type-specific).

Each `event_type` has its own required payload schema; a 400 with pydantic error details tells you what's missing.

For our subdomain use `well-knowns` (the resolved.sh subdomain, not the custom domain).
